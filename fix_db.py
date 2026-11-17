import sqlite3
conn = sqlite3.connect("database.db")
cur = conn.cursor()
cur.execute("DELETE FROM devices")
devices = [
    ('Main-Router','192.168.40.1','router',40),
    ('Core-Switch','192.168.40.2','core_switch',40),
    ('Server-PC','192.168.40.11','server',40),
    ('Admin-PC1','192.168.10.11','pc',10),
    ('Admin-PC2','192.168.10.12','pc',10),
    ('Lab-PC1','192.168.20.11','pc',20),
    ('Lab-PC2','192.168.20.12','pc',20),
    ('Lab-PC3','192.168.20.13','pc',20),
    ('Lab-PC4','192.168.20.14','pc',20),
    ('Library-PC1','192.168.30.11','pc',30),
    ('Library-PC2','192.168.30.12','pc',30),
]
cur.executemany("INSERT INTO devices (device_name, ip_address, device_type, vlan_id) VALUES (?,?,?,?)", devices)
conn.commit()
print("Done! 11 devices daal diye")
conn.close()
