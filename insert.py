# insert.py - Insert Devices into Database
# Fixed version - Matched with devices.py + schema-1.sql + seed-rules.sql
import sqlite3
from devices import DEVICES

DB_PATH = 'network_monitor.db'

conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA foreign_keys = ON")
c = conn.cursor()

# Clean old data - Delete child tables first to avoid foreign key error
c.execute("DELETE FROM rule_firings")
c.execute("DELETE FROM faults")
c.execute("DELETE FROM fault_history")
c.execute("DELETE FROM metrics")
c.execute("DELETE FROM test_scenarios")
c.execute("DELETE FROM devices")
# Reset autoincrement so IDs start from 1 again
c.execute("DELETE FROM sqlite_sequence WHERE name='devices'")

# --- Insert devices with interfaces: Router + Core Switch ---
for d in DEVICES:
    if d.interfaces:
        for x in d.interfaces:
            # FIX 1: Correct device_type - Router stays router, Core stays core_switch
            # Before: Always "router" - Core Switch was wrongly inserted as router
            if d.type == "router":
                device_type = "router"
            elif d.type == "core_switch":
                device_type = "core_switch"
            else:
                device_type = d.type

            # FIX 2: Clean device_name with separator
            # Before: d.name + x.service = "Main-RouterAdmin-GW" (no separator)
            # After:  "Main-Router-Admin-GW" (readable)
            device_name = f"{d.name}-{x.service}"

            c.execute(
                "INSERT INTO devices(device_name, ip_address, device_type, vlan_id, location, status) VALUES (?,?,?,?,?,?)",
                (device_name, x.ip, device_type, x.vlan, x.service, "unknown")
            )

# --- Insert devices without interfaces: Hosts + Server ---
for d in DEVICES:
    if not d.interfaces:
        # FIX 3: Correct device_type - Server stays server, Host stays pc
        # Before: Always "pc" - Server-PC was wrongly inserted as pc
        # After:  Server -> server, Host -> pc
        if d.type == "server":
            device_type = "server"
        elif d.type == "host":
            device_type = "pc"
        else:
            device_type = d.type

        c.execute(
            "INSERT INTO devices(device_name, ip_address, device_type, vlan_id, location, status) VALUES (?,?,?,?,?,?)",
            (d.name, d.ip, device_type, d.vlan, d.name, "unknown")
        )

conn.commit()

# Verification - Must be 12
count = c.execute("SELECT COUNT(*) FROM devices").fetchone()[0]
print(f"Inserted: {count} (Expected: 12)")

# Verify types - Must show correct counts
print("\nVerification by type:")
for row in c.execute("SELECT device_type, COUNT(*) FROM devices GROUP BY device_type"):
    print(f"  {row[0]}: {row[1]}")

# Expected: router: 4, core_switch: 4, pc: 3, server: 1
router_count = c.execute("SELECT COUNT(*) FROM devices WHERE device_type='router'").fetchone()[0]
core_count = c.execute("SELECT COUNT(*) FROM devices WHERE device_type='core_switch'").fetchone()[0]
pc_count = c.execute("SELECT COUNT(*) FROM devices WHERE device_type='pc'").fetchone()[0]
server_count = c.execute("SELECT COUNT(*) FROM devices WHERE device_type='server'").fetchone()[0]

if count == 12 and router_count == 4 and core_count == 4 and pc_count == 3 and server_count == 1:
    print("\nSUCCESS: All devices inserted correctly")
else:
    print("\nERROR: Counts do not match expected values")
    print("Expected: Total 12, Router 4, Core 4, PC 3, Server 1")

conn.close()
