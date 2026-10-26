import sqlite3, datetime, subprocess, re
from devices import DEVICES

def ping_ip(ip):
    try:
        r=subprocess.run(["ping","-c","1","-W","1",ip],capture_output=True,text=True)
        up=r.returncode==0
        m=re.search(r"time=([0-9.]+)",r.stdout)
        lat=float(m.group(1)) if m else 0.0
        return up,lat
    except:
        return False,0.0

conn=sqlite3.connect('database.db')
c=conn.cursor()

# get one rule_id for faults (R01)
row=c.execute("SELECT rule_id FROM rules LIMIT 1").fetchone()
default_rule_id=row[0] if row else "R01_CORE_DOWN"

print(f"Using rule_id={default_rule_id} for faults")

mp={}
for r in c.execute("SELECT device_id, device_name, ip_address FROM devices").fetchall():
    did,nm,ip=r
    mp[ip]=did
    mp[nm]=did

down_list=[]
for d in DEVICES:
    t=[]
    if getattr(d,'interfaces',None):
        for x in d.interfaces: t.append((d.name+x.service,x.ip))
    else: t.append((d.name,d.ip))
    for name,ip in t:
        up,lat=ping_ip(ip)
        did=mp.get(ip) or mp.get(name)
        if not did: continue
        now=datetime.datetime.now().isoformat()
        c.execute("INSERT INTO metrics(device_id,timestamp,icmp_status,latency_ms,packet_loss_percent) VALUES (?,?,?,?,?)",(did,now,1 if up else 0,lat,0 if up else 100))
        print(f"[{'UP' if up else 'DOWN'}] {name} id={did} {lat}ms")
        if not up:
            down_list.append((did,name,ip))
            # Insert into faults with YOUR schema: device_id, rule_id, status, evidence
            c.execute("INSERT INTO faults(device_id,rule_id,status,evidence,detected_at) VALUES (?,?,?,?,?)",
                      (did,default_rule_id,"OPEN",f"{name} {ip} unreachable - latency {lat}ms",now))

conn.commit()

# Rule execution log
if down_list:
    now=datetime.datetime.now().isoformat()
    for did,name,ip in down_list:
        c.execute("INSERT INTO rule_execution_log(rule_id,device_id,result,details,executed_at) VALUES (?,?,?,?,?)",
                  (default_rule_id,did,"FAIL",f"Rule fired: {name} DOWN - {ip}",now))
    conn.commit()
    print(f"Rule {default_rule_id} fired for {len(down_list)} devices")

print(f"--- FINAL COUNT ---")
print(f"Metrics: {c.execute('SELECT COUNT(*) FROM metrics').fetchone()[0]}")
print(f"Faults: {c.execute('SELECT COUNT(*) FROM faults').fetchone()[0]}")
print(f"RuleLogs: {c.execute('SELECT COUNT(*) FROM rule_execution_log').fetchone()[0]}")
conn.close()
