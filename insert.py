# insert.py - Insert Devices into Database
# FINAL Fixed version - 100% Matched with EVE-NG Topology Photo
# Topology: 1 Router + 1 Core Switch + 1 Server + 8 PCs = 11 Devices
import sqlite3
from devices import DEVICES

DB_PATH = 'network_monitor.db'

conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA foreign_keys = ON")
c = conn.cursor()

# Clean old data
c.execute("DELETE FROM rule_firings")
c.execute("DELETE FROM faults")
c.execute("DELETE FROM fault_history")
c.execute("DELETE FROM metrics")
c.execute("DELETE FROM test_scenarios")
c.execute("DELETE FROM devices")
c.execute("DELETE FROM sqlite_sequence WHERE name='devices'")

# --- 1 Device = 1 Row ---
for d in DEVICES:
    # Type fix: host -> pc
    if d.type == "host":
        device_type = "pc"
    else:
        device_type = d.type

    # --- IP ka FIX: Pehle d.ip check karo, agar khali hai to interfaces se lo ---
    ip = getattr(d, 'ip', None)
    if not ip and d.interfaces:
        ip = d.interfaces[0].ip
    if not ip:
        ip = "0.0.0.0"  # Kabhi khali nahi jayega, isliye error nahi aayega

    # --- VLAN ka FIX ---
    vlan = getattr(d, 'vlan', None)
    if vlan is None and d.interfaces:
        vlan = d.interfaces[0].vlan
    if vlan is None:
        vlan = 1

    c.execute(
        "INSERT INTO devices(device_name, ip_address, device_type, vlan_id, location, status) VALUES (?,?,?,?,?,?)",
        (d.name, ip, device_type, vlan, d.name, "unknown")
    )

conn.commit()

# Verification - Must be 11
count = c.execute("SELECT COUNT(*) FROM devices").fetchone()[0]
print(f"Inserted: {count} (Expected: 11)")

print("\nVerification by type:")
for row in c.execute("SELECT device_type, COUNT(*) FROM devices GROUP BY device_type"):
    print(f"  {row[0]}: {row[1]}")

router_count = c.execute("SELECT COUNT(*) FROM devices WHERE device_type='router'").fetchone()[0]
core_count = c.execute("SELECT COUNT(*) FROM devices WHERE device_type='core_switch'").fetchone()[0]
pc_count = c.execute("SELECT COUNT(*) FROM devices WHERE device_type='pc'").fetchone()[0]
server_count = c.execute("SELECT COUNT(*) FROM devices WHERE device_type='server'").fetchone()[0]

if count == 11 and router_count == 1 and core_count == 1 and pc_count == 8 and server_count == 1:
    print("\nSUCCESS: All devices inserted correctly - Topology Matched 100%")
else:
    print("\nERROR: Counts do not match expected values")
    print("Expected: Total 11, Router 1, Core 1, PC 8, Server 1")

print("\nAll Devices:")
for row in c.execute("SELECT device_name, ip_address, device_type FROM devices ORDER BY ip_address"):
    print(f"  {row[0]} - {row[1]} - {row[2]}")

conn.close()
