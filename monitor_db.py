import sqlite3
import datetime
from devices import DEVICES
from monitor_v2 import ping_device  # uses your existing ping

conn=sqlite3.connect('database.db')
c=conn.cursor()

for d in DEVICES:
  ips = []
  if d.interfaces:
    for x in d.interfaces:
      ips.append((d.name+x.service, x.ip))
  else:
    ips.append((d.name, d.ip))
  
  for name,ip in ips:
    result = ping_device(ip)  # returns UP/DOWN and ms
    status = "up" if result["up"] else "down"
    latency = result.get("latency", 0)
    
    # Write to metrics table (for Grafana)
    c.execute("INSERT INTO metrics(device_name,metric_type,metric_value,timestamp) VALUES (?,?,?,?)",
              (name, "ping_latency", latency, datetime.datetime.now().isoformat()))
    c.execute("INSERT INTO metrics(device_name,metric_type,metric_value,timestamp) VALUES (?,?,?,?)",
              (name, "status", 1 if status=="up" else 0, datetime.datetime.now().isoformat()))
    
    # Write to faults if DOWN
    if status=="down":
      c.execute("INSERT INTO faults(device_name,fault_type,description,timestamp) VALUES (?,?,?,?)",
                (name, "DEVICE_DOWN", f"{name} {ip} is DOWN", datetime.datetime.now().isoformat()))
    print(f"[{status.upper()}] {name} -> logged")

conn.commit()
print("Metrics logged:", c.execute("SELECT COUNT(*) FROM metrics").fetchone()[0])
conn.close()
