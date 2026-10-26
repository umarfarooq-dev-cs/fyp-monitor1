import sqlite3
import datetime
import subprocess
import re
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

# Check metrics columns automatically
cols = [x[1] for x in c.execute("PRAGMA table_info(metrics)").fetchall()]
print("metrics columns:", cols)

for d in DEVICES:
    targets = []
    if d.interfaces:
        for x in d.interfaces:
            targets.append((d.name+x.service, x.ip))
    else:
        targets.append((d.name, d.ip))
    
    for name, ip in targets:
        up, lat = ping_ip(ip)
        status = "up" if up else "down"
        now = datetime.datetime.now().isoformat()
        
        # Insert into metrics - try both possible schemas
        try:
            if "metric_value" in cols:
                c.execute("INSERT INTO metrics(device_name,metric_type,metric_value,timestamp) VALUES (?,?,?,?)",
                          (name, "latency", lat, now))
                c.execute("INSERT INTO metrics(device_name,metric_type,metric_value,timestamp) VALUES (?,?,?,?)",
                          (name, "status", 1 if up else 0, now))
            else:
                # fallback if table is id, device_id, value etc
                c.execute("INSERT INTO metrics(device_name,metric_type,metric_value,timestamp) VALUES (?,?,?,?)",
                          (name, "latency", lat, now))
        except Exception as e:
            print(f"metrics insert failed for {name}: {e}")
        
        if not up:
            try:
                c.execute("INSERT INTO faults(device_name,fault_type,description,timestamp) VALUES (?,?,?,?)",
                          (name, "DOWN", f"{name} {ip} DOWN", now))
            except:
                pass
        
        print(f"[{'UP' if up else 'DOWN'}] {name} ({ip}) - {lat}ms -> logged")

conn.commit()
print("Total metrics:", c.execute("SELECT COUNT(*) FROM metrics").fetchone()[0])
print("Total faults:", c.execute("SELECT COUNT(*) FROM faults").fetchone()[0])
conn.close()
