# devices.py - FINAL FIXED - Works with insert.py + monitor_v2.py + app.py
# Total: 1 Router + 1 Core Switch + 1 Server + 8 PCs = 11 Devices
from dataclasses import dataclass, field

@dataclass
class Interface:
    ip: str
    vlan: int
    service: str

@dataclass
class Device:
    name: str
    type: str
    ip: str
    vlan: int
    interfaces: list = field(default_factory=list)

    # --- YE 2 CHEEZEN ISILIYE ADD KI HAIN TAAKE monitor_v2.py KABHI ERROR NA DE ---
    # monitor_v2.py t.get("type") karta hai, isliye Device ko bhi .get() de diya
    def get(self, key, default=None):
        # name, ip, type, vlan sab ko dict jaisa bana diya
        mapping = {
            "name": self.name,
            "device_name": self.name,
            "ip": self.ip,
            "ip_address": self.ip,
            "type": self.type,
            "device_type": self.type,
            "vlan": self.vlan,
            "vlan_id": self.vlan,
            "location": self.name,
        }
        return mapping.get(key, default)

    def __getitem__(self, key):
        return self.get(key)

DEVICES = [
    Device("Main-Router", "router", "192.168.10.1", 10, [Interface("192.168.10.1", 10, "Main-GW")]),
    Device("Core-Switch-SW1", "core_switch", "192.168.10.2", 10, [Interface("192.168.10.2", 10, "Core-SW")]),
    Device("Server-PC", "server", "192.168.40.11", 40, []),
    Device("Admin-PC1", "host", "192.168.10.11", 10, []),
    Device("Admin-PC2", "host", "192.168.10.12", 10, []),
    Device("Lab-PC1", "host", "192.168.20.11", 20, []),
    Device("Lab-PC2", "host", "192.168.20.12", 20, []),
    Device("Lab-PC3", "host", "192.168.20.13", 20, []),
    Device("Lab-PC4", "host", "192.168.20.14", 20, []),
    Device("Library-PC1", "host", "192.168.30.11", 30, []),
    Device("Library-PC2", "host", "192.168.30.12", 30, []),
]

# monitor_v2.py ke liye - dict wali list
FLAT_TARGETS = [
    {
        "name": d.name,
        "device_name": d.name,
        "ip": d.ip,
        "ip_address": d.ip,
        "type": d.type,
        "device_type": d.type,
        "vlan": d.vlan,
        "vlan_id": d.vlan,
        "location": d.name,
    }
    for d in DEVICES
]
