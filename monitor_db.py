import subprocess, sqlite3, time, sys, socket, urllib.request, urllib.error, re, os, json
DB="database.db"; PING_COUNT=1; PING_TIMEOUT=1; CHECK_INTERVAL=60
GATEWAYS={"10":"192.168.10.1","20":"192.168.20.1","30":"192.168.30.1","40":"192.168.40.1"}
STATE_FILE="monitor_state.json"
LOCKED_TARGETS=[(1,"Main-Router-VLAN10","192.168.10.1","router","10"),(2,"Main-Router-VLAN20","192.168.20.1","router","20"),(3,"Main-Router-VLAN30","192.168.30.1","router","30"),(4,"Main-Router-VLAN40","192.168.40.1","router","40"),(5,"Core-Switch-VLAN10","192.168.10.2","core_switch","10"),(6,"Core-Switch-VLAN20","192.168.20.2","core_switch","20"),(7,"Core-Switch-VLAN30","192.168.30.2","core_switch","30"),(8,"Core-Switch-VLAN40","192.168.40.2","core_switch","40"),(9,"Admin-PC","192.168.10.11","pc","10"),(10,"Lab-PC","192.168.20.11","pc","20"),(11,"Library-PC","192.168.30.11","pc","30"),(12,"Server-PC","192.168.40.11","server","40")]
def ping_ip(ip):
    try:
        r=subprocess.run(["ping","-c",str(PING_COUNT),"-W",str(PING_TIMEOUT),ip],capture_output=True,text=True,timeout=5)
        loss=100.0; latency=None
        for line in r.stdout.splitlines():
            if "packet loss" in line:
                m=re.search(r"(\d+)% packet loss",line)
                if m: loss=float(m.group(1))
            if "rtt min/avg" in line or "round-trip" in line:
                try: latency=float(line.split("=")[1].split("/")[1])
                except: latency=None
        if r.returncode==0: return 1,latency,loss
        return 0,None,100.0
    except: return 0,None,100.0
def check_http(ip):
    try:
        req=urllib.request.Request(f"http://{ip}",method='GET')
        with urllib.request.urlopen(req,timeout=3) as resp: return resp.status
    except urllib.error.HTTPError as e: return e.code
    except: return 0
def check_dns():
    try: socket.gethostbyname("google.com"); return 1
    except: return 0
def check_dns_time():
    try:
        s=time.time(); socket.gethostbyname("google.com"); return round((time.time()-s)*1000,2)
    except: return None
def check_snmp(ip,oid):
    try:
        r=subprocess.run(["snmpwalk","-v2c","-c","public","-t","2","-r","1",ip,oid],capture_output=True,text=True,timeout=3)
        if r.returncode==0 and "INTEGER" in r.stdout:
            m=re.search(r"INTEGER:\s*(\d+)",r.stdout)
            if m: return float(m.group(1))
        return None
    except: return None
def snmp_pct(ip,a,b):
    try:
        u=check_snmp(ip,a); t=check_snmp(ip,b)
        if u is not None and t is not None and t>0: return round((u/t)*100,2)
        return None
    except: return None
def get_arp():
    d={}
    try:
        r=subprocess.run(["arp","-a"],capture_output=True,text=True,timeout=5)
        for line in r.stdout.splitlines():
            m=re.search(r"\((\d+\.\d+\.\d+\.\d+)\) at ([0-9a-f:]+)",line)
            if m: d[m.group(1)]=m.group(2)
    except: pass
    return d
def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f: return json.load(f)
        except: return {}
    return {}
def save_state(s):
    try:
        with open(STATE_FILE,"w") as f: json.dump(s,f)
    except: pass
def rule_for(t): return {"router":"R01","core_switch":"R06","switch":"R06","server":"R07","pc":"R08"}.get(t,"R01")
def details(cur,rid):
    cur.execute("SELECT rule_name,probable_cause,recommended_action,verification_step FROM rules WHERE rule_id=?",(rid,))
    r=cur.fetchone()
    return r if r else ("Unknown","Unknown","Check","Ping")
def log(cur,rid,did,res,det): cur.execute("INSERT INTO rule_firings (rule_id,device_id,result,details) VALUES (?,?,?,?)",(rid,did,res,det))
def mk_fault(cur,did,rid,ev,msg,sev="Critical"):
    cur.execute("SELECT fault_id FROM faults WHERE device_id=? AND rule_id=? AND status='open'",(did,rid))
    if cur.fetchone(): log(cur,"R15",did,"fired",f"Duplicate {rid} suppressed"); return False
    cur.execute("INSERT INTO faults (device_id,rule_id,status,evidence) VALUES (?,?,'open',?)",(did,rid,ev))
    cur.execute("INSERT INTO fault_history (device_id,severity,message) VALUES (?,?,?)",(did,sev,msg))
    return True
def resolve_all(cur,did):
    cur.execute("SELECT fault_id,rule_id FROM faults WHERE device_id=? AND status='open'",(did,))
    for fid,rid in cur.fetchall():
        cur.execute("UPDATE faults SET status='resolved',resolved_at=CURRENT_TIMESTAMP WHERE fault_id=?",(fid,))
        cur.execute("INSERT INTO fault_history (device_id,severity,message) VALUES (?, 'Info', ?)",(did,f"Device recovered - Fault {rid} resolved (R10)"))
        log(cur,"R10",did,"fired","Device recovered")
def resolve_one(cur,did,rid):
    cur.execute("SELECT fault_id FROM faults WHERE device_id=? AND rule_id=? AND status='open'",(did,rid))
    r=cur.fetchone()
    if r:
        cur.execute("UPDATE faults SET status='resolved',resolved_at=CURRENT_TIMESTAMP WHERE fault_id=?",(r[0],))
        cur.execute("INSERT INTO fault_history (device_id,severity,message) VALUES (?, 'Info', ?)",(did,f"Condition OK - Fault {rid} auto-resolved"))
        log(cur,"R10",did,"fired",f"{rid} auto-resolved")
def hourly(cur,did,up):
    cur.execute("""INSERT INTO metrics_hourly (device_id,hour_start,avg_latency_ms,max_packet_loss,up_count,down_count) VALUES (?,strftime('%Y-%m-%d %H:00:00','now'),NULL,NULL,?,?) ON CONFLICT(device_id,hour_start) DO UPDATE SET up_count=up_count+excluded.up_count,down_count=down_count+excluded.down_count""",(did,1 if up==1 else 0,1 if up==0 else 0))
def init_db(cur):
    cur.execute("""CREATE TABLE IF NOT EXISTS devices (device_id INTEGER PRIMARY KEY,device_name TEXT,ip_address TEXT,device_type TEXT,vlan_id TEXT,status TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS rules (rule_id TEXT PRIMARY KEY,rule_name TEXT,probable_cause TEXT,recommended_action TEXT,verification_step TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS metrics (id INTEGER PRIMARY KEY AUTOINCREMENT,device_id INTEGER,icmp_status INTEGER,latency_ms REAL,packet_loss_percent REAL,http_status INTEGER,snmp_cpu_percent REAL,interface_status TEXT,port_status TEXT,dns_status INTEGER,ip_address_assigned TEXT,timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS faults (fault_id INTEGER PRIMARY KEY AUTOINCREMENT,device_id INTEGER,rule_id TEXT,status TEXT,evidence TEXT,resolved_at TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS fault_history (id INTEGER PRIMARY KEY AUTOINCREMENT,device_id INTEGER,severity TEXT,message TEXT,timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS rule_firings (id INTEGER PRIMARY KEY AUTOINCREMENT,rule_id TEXT,device_id INTEGER,result TEXT,details TEXT,timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS metrics_hourly (device_id INTEGER,hour_start TEXT,avg_latency_ms REAL,max_packet_loss REAL,up_count INTEGER,down_count INTEGER,UNIQUE(device_id,hour_start))""")
    for did,name,ip,dt,vlan in LOCKED_TARGETS:
        cur.execute("INSERT OR REPLACE INTO devices VALUES (?,?,?,?,?,'UNKNOWN')",(did,name,ip,dt,vlan))
    seeds=[("R01","Device Unreachable","Power/cable","Check power","Ping 3 polls 100% + GW UP"),("R02","High Packet Loss","Loss >5%","Check cable","Ping"),("R03","High Latency Warning","Latency >100ms","Check util","Ping"),("R04","High Latency Critical","Latency >200ms","Check link","Ping"),("R05","Packet Loss / DHCP","Loss >5% or not in ARP","Check DHCP/ARP","ARP"),("R06","Uplink / Core Down","Core/GW down","Check core","Ping GW"),("R07","Server Down","Server off","Check server","Ping 3 polls"),("R08","PC Down","PC off","Check PC","Ping 3 polls"),("R09","Interface Flapping","Flapped 3+","Check port","Flaps"),("R10","Auto Resolve","Recovered","No action","Ping OK"),("R11","Link Saturated","Lat>200 + Loss>20%","Check util","Ping"),("R12","Port Down","Port down","Check port","Port"),("R13","VLAN Mismatch","VLAN missing","Assign VLAN","VLAN"),("R14","Duplicate IP","Same IP twice","Change IP","ARP"),("R15","Duplicate Suppression","Already open","Suppress","Faults"),("R16","Gateway Down","GW unreachable","Check router","Ping GW"),("R17","DNS Failure","Ping UP DNS fail","Check DNS","nslookup"),("R18","Slow DNS","DNS >2000ms","Check DNS","DNS time"),("R19","High CPU","CPU >85%","Check process","SNMP"),("R20","High Memory","MEM >85%","Check process","SNMP"),("R21","High Disk Usage","Disk >85%","Free disk","SNMP"),("R22","HTTP Down","Ping UP HTTP 0","Restart service","curl"),("R23","Unauthorized Device","ARP not in DB","Block","ARP"),("R24","Link / Cable Down","Link down","Check cable","Ping"),("R25","Stale / No Data","No metrics 3 cycles","Check monitor","Metrics")]
    for rid,n,c,a,v in seeds: cur.execute("INSERT OR REPLACE INTO rules VALUES (?,?,?,?,?)",(rid,n,c,a,v))
def fails3(cur,did):
    cur.execute("SELECT packet_loss_percent FROM metrics WHERE device_id=? ORDER BY id DESC LIMIT 3",(did,))
    rows=cur.fetchall()
    return len(rows)>=3 and all(r[0]==100.0 for r in rows)
def warn(cur,did,rid,ev,msg):
    if mk_fault(cur,did,rid,ev,msg,"Warning"): log(cur,rid,did,"fired",ev)
def main():
    conn=sqlite3.connect(DB); cur=conn.cursor(); init_db(cur); conn.commit()
    dns_ok=check_dns(); dns_time=check_dns_time(); state=load_state(); arp=get_arp()
    cur.execute("SELECT device_id,device_name,ip_address,device_type,vlan_id FROM devices ORDER BY device_id")
    all_dev=cur.fetchall()
    gw_st={}
    for vlan,gw in GATEWAYS.items():
        u,_,_=ping_ip(gw); gw_st[vlan]=u
        if u==0: print(f"R16 CRITICAL: Gateway {gw} (VLAN {vlan}) DOWN!",flush=True)
    seen={}; devices=[]
    for d in all_dev:
        did,name,ip,dt,vlan=d
        if ip in seen:
            print(f"R14 DUPLICATE IP: {name} [{ip}] duplicate of {seen[ip]}",flush=True); mk_fault(cur,did,"R14",f"Duplicate IP {ip}",f"[R14] {name} Duplicate IP {ip}","Critical"); log(cur,"R14",did,"fired",f"Duplicate {ip}"); continue
        seen[ip]=did; devices.append(d)
    for aip,mac in arp.items():
        if aip.startswith("192.168.") and aip not in seen and aip not in GATEWAYS.values():
            print(f"R23 UNAUTHORIZED: {aip} MAC {mac}",flush=True); log(cur,"R23",1,"fired",f"Unauthorized {aip} {mac}")
    print(f"\n--- Monitoring {len(devices)} targets | DNS: {'OK' if dns_ok else 'FAIL'} ({dns_time}ms) | GW: {gw_st} ---",flush=True)
    for did,name,ip,dt,vlan in devices:
        gw_up=gw_st.get(str(vlan),1)
        up,lat,loss=ping_ip(ip); status="UP" if up==1 else "DOWN"
        http=check_http(ip) if dt=="server" else None
        cpu=check_snmp(ip,"1.3.6.1.2.1.25.3.3.1.2") if dt in ("router","core_switch","server") else None
        mem=snmp_pct(ip,"1.3.6.1.2.1.25.2.3.1.6.1","1.3.6.1.2.1.25.2.3.1.5.1") if dt in ("router","server") else None
        disk=snmp_pct(ip,"1.3.6.1.2.1.25.2.3.1.6.2","1.3.6.1.2.1.25.2.3.1.5.2") if dt in ("router","server") else None
        print(f"{status} {name} [{ip}] latency={lat} loss={loss}% HTTP={http} CPU={cpu} MEM={mem} DISK={disk}",flush=True)
        k=str(did); prev=state.get(k,{"last":status,"flaps":0})
        prev["flaps"]=prev.get("flaps",0)+1 if prev["last"]!=status else 0; prev["last"]=status; state[k]=prev
        is_f=(up==0) or (loss>5) or (lat is not None and lat>200) or (http==0 and dt=="server")
        if is_f: cur.execute("INSERT INTO metrics (device_id,icmp_status,latency_ms,packet_loss_percent,http_status,snmp_cpu_percent,interface_status,port_status,dns_status,ip_address_assigned) VALUES (?,?,?,?,?,?,?,?,?,?)",(did,up,lat,loss,http,cpu,status,status,dns_ok,ip))
        else: hourly(cur,did,up)
        cur.execute("UPDATE devices SET status=? WHERE device_id=?",(status,did))
        if up==0:
            if gw_up==1 and fails3(cur,did):
                rid=rule_for(dt); n,c,a,v=details(cur,rid); ev=f"3 polls 100%, GW {GATEWAYS.get(str(vlan))}=UP"
                if mk_fault(cur,did,rid,ev,f"[{rid}] {name} DOWN - {c}. {a}","Critical"): log(cur,rid,did,"fired",ev); print(f"  -> FAULT: {rid} - {name}",flush=True)
                if rid!="R01": log(cur,"R01",did,"fired",f"Unreachable via {rid}")
            elif gw_up==0: print(f"  -> R06: {name} DOWN but GW DOWN - suppress R01",flush=True)
            if dt in ("switch","core_switch"): warn(cur,did,"R12",f"Port DOWN {name}",f"[R12] {name} Port DOWN")
            if dt in ("router","core_switch","switch"): warn(cur,did,"R24",f"Link DOWN {ip}",f"[R24] {name} Link Down")
        else:
            resolve_all(cur,did)
            if loss>5: warn(cur,did,"R02",f"Loss {loss}% >5%",f"[R02] {name} Loss {loss}%")
            else: resolve_one(cur,did,"R02")
            if lat is not None and lat>100: warn(cur,did,"R03",f"Latency {lat}>100",f"[R03] {name} Lat {lat}")
            else: resolve_one(cur,did,"R03")
            if lat is not None and lat>200: warn(cur,did,"R04",f"Latency {lat}>200",f"[R04] {name} Lat {lat}")
            else: resolve_one(cur,did,"R04")
            if lat is not None and lat>200 and loss>20: warn(cur,did,"R11",f"Lat {lat} + Loss {loss}%",f"[R11] {name} Saturated")
            else: resolve_one(cur,did,"R11")
            if prev.get("flaps",0)>=3: warn(cur,did,"R09",f"Flapped {prev['flaps']}",f"[R09] {name} Flapping"); state[k]["flaps"]=0
            if dt in ("switch","core_switch","pc") and (vlan is None or vlan==""): warn(cur,did,"R13","VLAN missing",f"[R13] {name} VLAN")
            if dt=="server" and http==0: warn(cur,did,"R22","Ping UP HTTP 0",f"[R22] {name} HTTP DOWN")
            if dt=="server" and http not in (None,0,200): warn(cur,did,"R04",f"HTTP {http}",f"[R04] {name} HTTP {http}")
            else:
                if dt=="server": resolve_one(cur,did,"R22")
            if cpu is not None and cpu>85: warn(cur,did,"R19",f"CPU {cpu}>85",f"[R19] {name} CPU {cpu}")
            else: resolve_one(cur,did,"R19")
            if mem is not None and mem>85: warn(cur,did,"R20",f"MEM {mem}>85",f"[R20] {name} MEM {mem}")
            else: resolve_one(cur,did,"R20")
            if disk is not None and disk>85: warn(cur,did,"R21",f"Disk {disk}>85",f"[R21] {name} Disk {disk}")
            else: resolve_one(cur,did,"R21")
            if dns_ok==0: warn(cur,did,"R17","Ping UP DNS fail",f"[R17] DNS fail")
            else: resolve_one(cur,did,"R17")
            if dns_time is not None and dns_time>2000: warn(cur,did,"R18",f"DNS {dns_time}>2000",f"[R18] Slow DNS {dns_time}")
            else: resolve_one(cur,did,"R18")
            if dt=="pc" and ip not in arp: warn(cur,did,"R05",f"PC UP not in ARP {ip}",f"[R05] {name} DHCP fail")
            else:
                if dt=="pc": resolve_one(cur,did,"R05")
            cur.execute("SELECT COUNT(*) FROM metrics WHERE device_id=? AND timestamp > datetime('now','-3 minutes')",(did,))
            if cur.fetchone()[0]==0: log(cur,"R25",did,"fired","No recent metrics - stale")
            else: resolve_one(cur,did,"R25")
    save_state(state); conn.commit(); conn.close(); print("Saved monitoring cycle",flush=True)
if __name__=="__main__":
    if len(sys.argv)>1 and sys.argv[1]=="--once": main()
    else:
        while True:
            try: main()
            except Exception as e: print(f"Monitor loop error: {e}",flush=True)
            time.sleep(CHECK_INTERVAL)
