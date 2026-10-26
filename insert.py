import sqlite3
from devices import DEVICES
conn=sqlite3.connect('database.db')
c=conn.cursor()
c.execute("DELETE FROM devices")
for d in DEVICES:
 for x in d.interfaces:
  c.execute("INSERT INTO devices(device_name,ip_address,device_type,vlan_id,location,status) VALUES (?,?,?,?,?,?)",(d.name+x.service,x.ip,"router",x.vlan,x.service,"unknown"))
for d in DEVICES:
 if not d.interfaces:
  c.execute("INSERT INTO devices(device_name,ip_address,device_type,vlan_id,location,status) VALUES (?,?,?,?,?,?)",(d.name,d.ip,"pc",d.vlan or 0,d.name,"unknown"))
conn.commit()
print("Inserted:", c.execute("SELECT COUNT(*) FROM devices").fetchone()[0])
conn.close()
