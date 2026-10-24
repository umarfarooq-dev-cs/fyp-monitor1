# devices.py - Network Devices Inventory
# This file defines your whole EVE-NG topology
# Python ignores lines starting with # (these are comments for you)

from dataclasses import dataclass  # For creating clean device structures
from typing import List

@dataclass
class Interface:
    # Router interface with VLAN and IP
    name: str       # e.g. e0/0.10
    vlan: int       # e.g. 10, 20, 30, 40
    ip: str         # e.g. 192.168.10.1 (gateway)
    service: str    # Description e.g. Admin-GW

@dataclass
class Device:
    # Any network device
    id: int
    name: str
    type: str       # router, switch, host, server
    ip: str = None
    interfaces: List[Interface] = None  # Only router has multiple interfaces
    vlan: int = None

# --- ROUTER SUB-INTERFACES (4 VLANs on Main-Router) ---
# In EVE-NG, you created these on Router e0/0
ROUTER_INTERFACES = [
    Interface(name="e0/0.10", vlan=10, ip="192.168.10.1", service="Admin-GW"),
    Interface(name="e0/0.20", vlan=20, ip="192.168.20.1", service="Lab-GW"),
    Interface(name="e0/0.30", vlan=30, ip="192.168.30.1", service="Library-GW"),
    Interface(name="e0/0.40", vlan=40, ip="192.168.40.1", service="Server-GW"),
]

# --- ALL DEVICES IN YOUR TOPOLOGY ---
DEVICES = [
    Device(id=1, name="Main-Router", type="router", interfaces=ROUTER_INTERFACES),
    Device(id=2, name="Core-Switch-SW1", type="switch", ip="192.168.40.2", vlan=40),
    Device(id=3, name="Admin-PC", type="host", ip="192.168.10.11", vlan=10),
    Device(id=4, name="Lab-PC", type="host", ip="192.168.20.11", vlan=20),
    Device(id=5, name="Library-PC", type="host", ip="192.168.30.11", vlan=30),
    Device(id=6, name="Server-PC", type="server", ip="192.168.40.11", vlan=40),
]

# --- FLAT LIST FOR MONITORING (Easy to ping) ---
# Convert above structure into simple list of IPs to check
FLAT_TARGETS = []
for dev in DEVICES:
    if dev.interfaces:  # Router has 4 interfaces
        for intf in dev.interfaces:
            FLAT_TARGETS.append({"device": dev.name, "interface": intf.name, "vlan": intf.vlan, "ip": intf.ip, "type": "router-interface"})
    else:  # Switch and PCs have single IP
        FLAT_TARGETS.append({"device": dev.name, "interface": "mgmt", "vlan": dev.vlan, "ip": dev.ip, "type": dev.type})

# Monitoring settings
CHECK_INTERVAL = 60   # Check every 60 seconds
PING_COUNT = 1        # 1 ping per device
PING_TIMEOUT = 2      # Wait 2 seconds
