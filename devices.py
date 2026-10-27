cat > monitor_db.py << 'PY'
from devices import FLAT_TARGETS
import subprocess
import time
from datetime import datetime

def ping(ip):
    try:
        result = subprocess.run(["ping", "-c", "1", "-W", "2", ip], capture_output=True, text=True)
        if result.returncode == 0:
            # extract time
            for line in result.stdout.splitlines():
                if "time=" in line:
                    ms = line.split("time=")[1].split(" ")[0]
                    return True, float(ms)
            return True, 0.0
        return False, 0.0
    except:
        return False, 0.0

print(f"Monitoring {len(FLAT_TARGETS)} targets...")
for target in FLAT_TARGETS:
    up, latency = ping(target['ip'])
    status = "UP" if up else "DOWN"
    print(f"{status} {target['device']} {target['interface']} {target['ip']} {latency}ms VLAN{target['vlan']}")

print(f"Metrics {len(FLAT_TARGETS)} checked at {datetime.now()}")
PY

python3 monitor_db.py
