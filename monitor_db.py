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

# Auto-detect columns for devices table
dev_cols = [x[1] for x in c.execute("PRAGMA table_info(devices)").fetchall()]
met_cols = [x[1] for x in c.execute("PRAGMA table_info(metrics)").fetchall()]
print("devices columns:", dev_cols)
print("metrics columns:", met_cols)

# Find id column in devices (could be id, device_id, etc)
id_col = None
for cand in ["device_id","id","deviceId","ID"]:
    if cand in dev_cols:
        id_col = cand
        break
id_col = id_col or dev_cols[0]

ip_col = "ip_address" if "ip_address" in dev_cols else "ip" if "ip" in dev_cols else dev_cols[1]
name_col = "device_name" if "device_name" in dev_cols else dev_cols[0]

print(f"Using devices.{id_col}, {name_col}, {ip_col}")

# Build map ip -> device_id
devices_map = {}
for row in c.execute(f"SELECT {id_col}, {name_col}, {ip_col} FROM devices").fetchall():
    did, dname, dip = row
    devices_map[dip] = did
    devices_map[dname] = did

for d in DEVICES:
    targets = []
    if getattr(d, 'interfaces', None):
        for x in d.interfaces:
            targets.append((d.name+x.service, x.ip))
    else:
        targets.append((d.name, d.ip))
    
    for name, ip in targets:
        up, lat = ping_ip(ip)
        device_id = devices_map.get(ip) or devices_map.get(name)
        if not device_id:
            # try lookup by ip in DB
            try:
                r = c.execute(f"SELECT {id_col} FROM devices WHERE {ip_col}=?", (ip,)).fetchone()
                if r: device_id = r[0]
            except: pass
        if not device_id:
            print(f"Skipping {name} {ip} - not in DB")
            continue
            
        now = datetime.datetime.now().isoformat()
        icmp = 1 if up else 0
        loss = 0 if up else 100
        
        # Insert with correct column names
        try:
            c.execute(f"INSERT INTO metrics(device_id,timestamp,icmp_status,latency_ms,packet_loss_percent) VALUES (?,?,?,?,?)",
                      (device_id, now, icmp, lat, loss))
            print(f"[{'UP' if up else 'DOWN'}] {name} ({ip}) id={device_id} {lat}ms logged")
        except Exception as e:
            print(f"Insert failed for {name}: {e}")

conn.commit()
print("Total metrics:", c.execute("SELECT COUNT(*) FROM metrics").fetchone()[0])
try:
    print("Total faults:", c.execute("SELECT COUNT(*) FROM faults").fetchone()[0])
except:
    pass
conn.close()
