cat > monitor_db.py << 'ENDOFFILE'
import sqlite3
import datetime
import subprocess
import platform
import socket
import time

try:
    from devices import DEVICES
except ImportError:
    DEVICES = []

def ping_ip(ip, timeout=1):
    try:
        if not ip:
            return (False, 0.0)
        param = "-n" if platform.system().lower() == "windows" else "-c"
        if platform.system().lower() == "windows":
            cmd = ["ping", param, "1", "-w", str(timeout*1000), ip]
        else:
            cmd = ["ping", param, "1", "-W", str(timeout), ip]
        start = time.time()
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elapsed = (time.time() - start) * 1000
        return (result.returncode == 0, round(elapsed, 2) if result.returncode == 0 else 0.0)
    except Exception:
        return (False, 0.0)

def check_tcp(ip, port, timeout=2):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        result = s.connect_ex((ip, port))
        s.close()
        return 1 if result == 0 else 0
    except Exception:
        return 0

def check_http(ip, port=80, timeout=2):
    try:
        import http.client
        conn = http.client.HTTPConnection(ip, port, timeout=timeout)
        conn.request("GET", "/")
        resp = conn.getresponse()
        code = resp.status
        conn.close()
        return code
    except Exception:
        return None

def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS metrics(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER,
        timestamp TEXT,
        icmp_status INTEGER,
        latency_ms REAL,
        packet_loss INTEGER,
        http_status INTEGER,
        tcp_port_80_status INTEGER
    )""")
    conn.commit()
    return conn, c

if __name__ == "__main__":
    conn, c = init_db()
    print(f"Monitoring {len(DEVICES)} devices...")
    for dev in DEVICES:
        if isinstance(dev, dict):
            ip = dev.get('ip') or ''
            dev_id = dev.get('id') or 0
            dev_type = (dev.get('type') or 'host').lower()
            dev_name = dev.get('name') or ip or ''
        else:
            ip = getattr(dev, 'ip', '') or ''
            dev_id = getattr(dev, 'id', 0) or 0
            dev_type = (getattr(dev, 'type', 'host') or 'host').lower()
            dev_name = getattr(dev, 'name', '') or ip or ''

        up, lat = ping_ip(ip)
        icmp_status = 1 if up else 0
        packet_loss = 0 if up else 100
        http_status = None
        tcp_status = None
        if dev_type == 'server' or '40.10' in (ip or '') or 'server' in (dev_name or '').lower():
            tcp_status = check_tcp(ip, 80)
            http_status = check_http(ip, 80)

        c.execute("""INSERT INTO metrics(device_id, timestamp, icmp_status, latency_ms, packet_loss, http_status, tcp_port_80_status)
                     VALUES (?,?,?,?,?,?,?)""",
                  (dev_id, datetime.datetime.now().isoformat(), icmp_status, lat, packet_loss, http_status, tcp_status))
        print(f"{'UP' if up else 'DOWN'} {dev_name} {ip} {lat}ms TCP:{tcp_status} HTTP:{http_status}")

    conn.commit()
    print(f"Metrics {len(DEVICES)} inserted")
    conn.close()
ENDOFFILE
