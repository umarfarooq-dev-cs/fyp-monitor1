# devices.py - Device Definitions for FYP Network Monitor
# Matched with monitor_v2.py and seed-rules.sql
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Interface:
    name: str
    vlan: int
    ip: str
    service: str

@dataclass
class Device:
    id: int
    name: str
    type: str  # router / core_switch / host / server
    ip: Optional[str] = None
    interfaces: Optional[List[Interface]] = None
    vlan: Optional[int] = None

# Router - 4 VLAN Gateways
ROUTER_INTERFACES = [
    Interface("e0/0.10", 10, "192.168.10.1", "Admin-GW"),
    Interface("e0/0.20", 20, "192.168.20.1", "Lab-GW"),
    Interface("e0/0.30", 30, "192.168.30.1", "Library-GW"),
    Interface("e0/0.40", 40, "192.168.40.1", "Server-GW"),
]

# Core Switch - 4 VLAN Interfaces
CORE_INTERFACES = [
    Interface("Vlan10", 10, "192.168.10.2", "Core-VLAN10"),
    Interface("Vlan20", 20, "192.168.20.2", "Core-VLAN20"),
    Interface("Vlan30", 30, "192.168.30.2", "Core-VLAN30"),
    Interface("Vlan40", 40, "192.168.40.2", "Core-VLAN40"),
]

# Devices
DEVICES = [
    Device(1, "Main-Router", "router", interfaces=ROUTER_INTERFACES),
    Device(2, "Core-Switch-SW1", "core_switch", interfaces=CORE_INTERFACES),
    Device(3, "Admin-PC", "host", ip="192.168.10.11", vlan=10),
    Device(4, "Lab-PC", "host", ip="192.168.20.11", vlan=20),
    Device(5, "Library-PC", "host", ip="192.168.30.11", vlan=30),
    Device(6, "Server-PC", "server", ip="192.168.40.11", vlan=40),
]

# Flat Targets for monitor_v2.py
FLAT_TARGETS = []

for dev in DEVICES:
    if dev.interfaces:
        for intf in dev.interfaces:
            if dev.type == "router":
                flat_type = "router-interface"
            elif dev.type == "core_switch":
                flat_type = "core_switch"
            else:
                flat_type = dev.type

            FLAT_TARGETS.append({
                "device": dev.name,
                "interface": intf.name,
                "vlan": intf.vlan,
                "ip": intf.ip,
                "type": flat_type,
                "device_type": dev.type,
                "service": intf.service,
            })
    else:
        FLAT_TARGETS.append({
            "device": dev.name,
            "interface": "eth0",
            "vlan": dev.vlan,
            "ip": dev.ip,
            "type": dev.type,
            "device_type": dev.type,
            "service": f"{dev.name}-Service",
        })

# Settings - Must match rules time_window
CHECK_INTERVAL = 60
PING_COUNT = 3
PING_TIMEOUT = 2

# Self Check
if __name__ == "__main__":
    print(f"Total Targets: {len(FLAT_TARGETS)}")
    for t in FLAT_TARGETS:
        print(t)
    assert len(FLAT_TARGETS) == 12, f"Error: Expected 12 targets, got {len(FLAT_TARGETS)}"
    assert any(t["type"] == "router-interface" for t in FLAT_TARGETS), "Error: router-interface not found"
    assert any(t["type"] == "core_switch" for t in FLAT_TARGETS), "Error: core_switch not found"
    assert any(t["type"] == "server" for t in FLAT_TARGETS), "Error: server not found"
    print("devices.py OK - All types matched")
