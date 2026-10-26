import sqlite3, datetime, subprocess, re
from devices import DEVICES

def ping_ip(ip):
    try:
        r = subprocess.run(["ping","-c","1","-W","1",ip], capture_output=True, text=True)
        up = r.returncode == 0
        m = re.search(r"time=([0-9.]+)", r.stdout)
        lat = float(m.group(1)) if m else 0.0
        return up, lat
    except:
        return False, 0.0

conn=sqlite3.connect('database.db')
c=conn.cursor()

# Build ip -> device_id map from your 9 devices table
devices_map = {}
for row in c.execute("SELECT id, device_name, ip_address FROM devices").fetchall():
    did, dname, dip = row
    devices_map[dip] = did
    # also map by name for router interfaces
    devices_map[dname] = did

print(f"Found {len(devices_map)} device mappings from DB")

for d in DEVICES:
    targets = []
    if d.interfaces:
        for x in d.interfaces:
            targets.append((d.name+x.service, x.ip))
    else:
        targets.append((d.name, d.ip))
    
    for name, ip in targets:
        up, lat = ping_ip(ip)
        # Find device_id for this IP
        device_id = devices_map.get(ip)
        if not device_id:
            # try find by name
            for row in c.execute("SELECT id FROM devices WHERE device_name=?", (name,)).fetchall():
                device_id = row[0]
                break
        if not device_id:
            print(f"Skipping {name} - no id in DB")
            continue
            
        now = datetime.datetime.now().isoformat()
        icmp = 1 if up else 0
        loss = 0 if up else 100
        
        c.execute("INSERT INTO metrics(device_id,timestamp,icmp_status,latency_ms,packet_loss_percent) VALUES (?,?,?,?,?)",
                  (device_id, now, icmp, lat, loss))
        
        if not up:
            try:
                c.execute("INSERT INTO faults(device_id,fault_type,description,timestamp) VALUES (?,?,?,?)",
                          (device_id, "DOWN", f"{name} {ip} DOWN", now))
            except:
                # try other faults schema
                try:
                    c.execute("INSERT INTO faults(device_name,fault_type,description,timestamp) VALUES (?,?,?,?)",
                              (name, "DOWN", f"{ip} DOWN", now))
                except Exception as e:
                    print(f"faults insert failed: {e}")
        
        print(f"[{'UP' if up else 'DOWN'}] {name} ({ip}) id={device_id} - {lat}ms -> logged to metrics")

conn.commit()
print("Total metrics:", c.execute("SELECT COUNT(*) FROM metrics").fetchone()[0])
print("Total faults:", c.execute("SELECT COUNT(*) FROM faults").fetchone()[0])
conn.close()
