cat > monitor_db.py << 'PYEOF'
import sqlite3, datetime, subprocess, platform, socket, time
try:
    from devices import DEVICES
except:
    DEVICES=[]
def ping_ip(ip,t=1):
    try:
        if not ip: return False,0
        p="-n" if platform.system().lower()=="windows" else "-c"
        c=["ping",p,"1","-w",str(t*1000),ip] if platform.system().lower()=="windows" else ["ping",p,"1","-W",str(t),ip]
        s=time.time(); r=subprocess.run(c,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); e=(time.time()-s)*1000
        return r.returncode==0, round(e,2) if r.returncode==0 else 0.0
    except: return False,0
def check_tcp(ip,port,t=2):
    try: s=socket.socket(); s.settimeout(t); r=s.connect_ex((ip,port)); s.close(); return 1 if r==0 else 0
    except: return 0
def check_http(ip,port=80,t=2):
    try:
        import http.client; conn=http.client.HTTPConnection(ip,port,timeout=t); conn.request("GET","/"); resp=conn.getresponse(); code=resp.status; conn.close(); return code
    except: return None
conn=sqlite3.connect("database.db"); cur=conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS metrics(id INTEGER PRIMARY KEY, device_id INTEGER, timestamp TEXT, icmp_status INTEGER, latency_ms REAL, packet_loss INTEGER, http_status INTEGER, tcp_port_80_status INTEGER)")
conn.commit()
print(f"Monitoring {len(DEVICES)} devices...")
for dev in DEVICES:
    ip=getattr(dev,'ip','') or ''; dev_id=getattr(dev,'id',0) or 0; dev_type=(getattr(dev,'type','host') or 'host').lower(); dev_name=getattr(dev,'name','') or ip or ''
    up,lat=ping_ip(ip); icmp=1 if up else 0; loss=0 if up else 100; http_s=None; tcp_s=None
    if dev_type=='server' or '40.10' in (ip or '') or 'server' in (dev_name or '').lower():
        tcp_s=check_tcp(ip,80); http_s=check_http(ip,80)
    cur.execute("INSERT INTO metrics(device_id,timestamp,icmp_status,latency_ms,packet_loss,http_status,tcp_port_80_status) VALUES (?,?,?,?,?,?,?)",(dev_id,datetime.datetime.now().isoformat(),icmp,lat,loss,http_s,tcp_s))
    print(f"{'UP' if up else 'DOWN'} {dev_name} {ip} {lat}ms TCP:{tcp_s} HTTP:{http_s}")
conn.commit(); print(f"Metrics {len(DEVICES)} inserted"); conn.close()
PYEOF
