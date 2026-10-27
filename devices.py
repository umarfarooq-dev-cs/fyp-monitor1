cat > devices.py << 'PY'
class Device:
    def __init__(self, id, name, ip, type="host"):
        self.id=id; self.name=name; self.ip=ip; self.type=type

# EXACT match to your EVE-NG config from photos
DEVICES = [
    # Gateways - Should be UP if EVE lab running
    Device(1, "Main-Router-VLAN10", "192.168.10.1", "router"),
    Device(2, "Main-Router-VLAN20", "192.168.20.1", "router"),
    Device(3, "Main-Router-VLAN30", "192.168.30.1", "router"),
    Device(4, "Main-Router-VLAN40", "192.168.40.1", "router"),
    Device(5, "Core-VLAN10", "192.168.10.2", "switch"),
    Device(6, "Core-VLAN20", "192.168.20.2", "switch"),
    Device(7, "Core-VLAN30", "192.168.30.2", "switch"),
    Device(8, "Core-VLAN40", "192.168.40.2", "switch"),
]
PY

python3 monitor_db.py
