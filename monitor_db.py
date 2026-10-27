import sqlite3, datetime, subprocess, re, socket
from devices import DEVICES
try:
    import requests
    HAS_REQUESTS = True
except:
    HAS_REQUESTS = False

def ping_ip(ip):
    try:
        r=subprocess.run(["ping","-c","1","-W","1",ip],capture_output=True,text=True)
        up=r.returncode==0
        m=re.search(r"time=([0-9.]+)",r.stdout)
        lat=float(m.group(1)) if m else 0.0
        return up,lat
    except: 
        return False,0.0

def check_tcp(ip, port=80, timeout=2):
    """R04: TCP Service check - lightweight socket"""
    try:
        sock=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result=sock.connect_ex((ip, port))
        sock.close()
        return 1 if result==0 else 0
    except:
        return 0

def check_http(ip, port=80, timeout=3):
    """R04: HTTP Service check - returns status code or 0"""
    if not HAS_REQUESTS:
        return 0
    try:
        url=f"http://{ip}:{port}" if port!=80 else f"http://{ip}"
        resp=requests.get(url, timeout=timeout)
        return resp.status_code
    except:
        return 0

# DB setup
conn=sqlite3.connect("database.db", timeout=10)
c=conn.cursor()

for dev in DEVICES:
    ip=dev['ip']
    dev_id=dev['id']
    dev_type=dev.get('type','host')
    
    # 1. ICMP - Existing
    up, lat = ping_ip(ip)
    icmp_status = 1 if up else 0
    packet_loss = 0 if up else 100
    
    # 2. NEW: TCP + HTTP only for Server (lightweight - not for all 9 devices)
    http_status = None
    tcp_status = None
    if dev_type=='server' or '40.10' in ip or 'server' in dev.get('name','').lower():
        tcp_status = check_tcp(ip, 80)
        http_status = check_http(ip, 80)
    
    # Insert into metrics - handles both old and new schema
    try:
        # Try new schema with http/tcp columns
        c.execute("""
            INSERT INTO metrics(device_id, timestamp, icmp_status, latency_ms, packet_loss, http_status, tcp_port_80_status)
            VALUES (?,?,?,?,?,?,?)
        """, (dev_id, datetime.datetime.now().isoformat(), icmp_status, lat, packet_loss, http_status, tcp_status))
    except sqlite3.OperationalError:
        # Fallback to old schema (only icmp columns) - if you haven't migrated yet
        c.execute("""
            INSERT INTO metrics(device_id, timestamp, icmp_status, latency_ms, packet_loss)
            VALUES (?,?,?,?,?)
        """, (dev_id, datetime.datetime.now().isoformat(), icmp_status, lat, packet_loss))
    
    print(f"[{'UP' if up else 'DOWN'}] {dev.get('name',ip)} {ip} {lat}ms TCP:{tcp_status} HTTP:{http_status}")

conn.commit()

# Rule engine logging (your existing logic for R01-R15)
# ... keep your existing fault + rule_execution_log inserts here ...

# Summary
m=c.execute("SELECT COUNT(*) FROM metrics").fetchone()[0]
f=c.execute("SELECT COUNT(*) FROM faults").fetchone()[0]
rl=c.execute("SELECT COUNT(*) FROM rule_execution_log").fetchone()[0]
print(f"Metrics {m} | Faults {f} | RuleLogs {rl}")

conn.close()
