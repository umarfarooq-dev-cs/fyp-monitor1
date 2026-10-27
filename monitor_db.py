import subprocess, platform, sqlite3
from devices import FLAT_TARGETS
from datetime import datetime

def ping_ip(ip):
    system = platform.system().lower()
    param = "-n" if system=="windows" else "-c"
    to = "-w" if system=="windows" else "-W"
    try:
        result = subprocess.run(["ping", param, "1", to, "1", ip], capture_output=True, text=True, timeout=3)
        return result.returncode == 0
    except:
        return False

conn = sqlite3.connect("monitor.db")
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS metrics (timestamp TEXT, device TEXT, ip TEXT, status TEXT)")
cur.execute("DELETE FROM metrics")
print(f"Monitoring {len(FLAT_TARGETS)} targets...")
for t in FLAT_TARGETS:
    ip = t['ip']
    dev = t['device']
    iface = t['interface']
    up = ping_ip(ip)
    status = "UP" if up else "DOWN"
    print(f"{status} {dev} {iface} {ip}")
    cur.execute("INSERT INTO metrics VALUES (?,?,?,?)", (datetime.now().isoformat(), dev, ip, status))
conn.commit()
conn.close()
print(f"Metrics {len(FLAT_TARGETS)} inserted")
