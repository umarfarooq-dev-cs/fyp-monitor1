cd ~/fyp-monitor1
rm devices.py

cat > devices.py << 'PY'
from dataclasses import dataclass
from typing import List
@dataclass
class Interface:
    name: str; vlan: int; ip: str; service: str
@dataclass
class Device:
    id: int; name: str; type: str; ip: str = None; interfaces: List[Interface] = None; vlan: int = None
ROUTER_INTERFACES = [
    Interface("e0/0.10",10,"192.168.10.1","Admin-GW"),
    Interface("e0/0.20",20,"192.168.20.1","Lab-GW"),
    Interface("e0/0.30",30,"192.168.30.1","Library-GW"),
    Interface("e0/0.40",40,"192.168.40.1","Server-GW"),
]
CORE_INTERFACES = [
    Interface("Vlan10",10,"192.168.10.2","Core-VLAN10"),
    Interface("Vlan20",20,"192.168.20.2","Core-VLAN20"),
    Interface("Vlan30",30,"192.168.30.2","Core-VLAN30"),
    Interface("Vlan40",40,"192.168.40.2","Core-VLAN40"),
]
DEVICES = [
    Device(1,"Main-Router","router",interfaces=ROUTER_INTERFACES),
    Device(2,"Core-Switch-SW1","switch",interfaces=CORE_INTERFACES),
    Device(3,"Admin-PC","host",ip="192.168.10.11",vlan=10),
    Device(4,"Lab-PC","host",ip="192.168.20.11",vlan=20),
    Device(5,"Library-PC","host",ip="192.168.30.11",vlan=30),
    Device(6,"Server-PC","server",ip="192.168.40.11",vlan=40),
]
FLAT_TARGETS=[]
for dev in DEVICES:
    if dev.interfaces:
        for intf in dev.interfaces:
            FLAT_TARGETS.append({"device":dev.name,"interface":intf.name,"vlan":intf.vlan,"ip":intf.ip,"type":dev.type})
    else:
        FLAT_TARGETS.append({"device":dev.name,"interface":"mgmt","vlan":dev.vlan,"ip":dev.ip,"type":dev.type})
CHECK_INTERVAL=60; PING_COUNT=1; PING_TIMEOUT=2
PY

cat devices.py | head -10
python3 monitor_db.py
