# devices.py - FINAL - 100% Matched with EVE-NG Topology
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
    type: str  # router, core_switch, server, host
    ip: str
    vlan: int
    interfaces: list = field(default_factory=list)

DEVICES = [
    Device("Main-Router", "router", "192.168.10.1", 10, [
        Interface("192.168.10.1", 10, "Main-GW"),
    ]),
    Device("Core-Switch-SW1", "core_switch", "192.168.10.2", 10, [
        Interface("192.168.10.2", 10, "Core-SW"),
    ]),
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

# --- YE LINE MISSING THI, ISILIYE ERROR AA RAHA THA ---
# monitor_v2.py isi ko import karta hai
FLAT_TARGETS = DEVICES
