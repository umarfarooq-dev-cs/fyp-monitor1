import sqlite3, datetime, subprocess, re
from devices import DEVICES

def ping_ip(ip):
    try:
        r=subprocess.run(["ping","-c","1","-W","1",ip],capture_output=True,text=True)
        up=r.returncode==0
        m=re.search(r"time=([0-9.]+)",r.stdout)
        lat=float(m.group(1)) if m else 0.0
        return up,lat
    except: return False,0.0

conn=sqlite3.connect('database.db')
c=conn.cursor()
rule_id=c.execute("SELECT rule_id FROM rules LIMIT 1").fetchone()[0]

mp={}
for r in c.execute("SELECT device_id, device_name, ip_address FROM devices").fetchall():
    did,nm,ip=r; mp[ip]=did; mp[nm]=did

down=0
for d in DEVICES:
    targets=[(d.name+x.service,x.ip) for x in d.interfaces] if getattr(d,'interfaces',None) else [(d.name,d.ip)]
    for name,ip in targets:
        up,lat=ping_ip(ip)
        did=mp.get(ip) or mp.get(name)
        if not did: continue
        now=datetime.datetime.now().isoformat()
        c.execute("INSERT INTO metrics(device_id,timestamp,icmp_status,latency_ms,packet_loss_percent) VALUES (?,?,?,?,?)",(did,now,1 if up else 0,lat,0 if up else 100))
        print(f"[{'UP' if up else 'DOWN'}] {name} {lat}ms")
        if not up:
            down+=1
            c.execute("INSERT INTO faults(device_id,rule_id,status,evidence,detected_at) VALUES (?,?,?,?,?)",(did,rule_id,"open",f"Ping failed for {name} {ip}",now))
            c.execute("INSERT INTO rule_execution_log(rule_id,device_id,result,details,executed_at) VALUES (?,?,?,?,?)",(rule_id,did,"fired",f"Rule {rule_id} fired: {name} DOWN - {ip}",now))

conn.commit()
print(f"Metrics {c.execute('SELECT COUNT(*) FROM metrics').fetchone()[0]} | Faults {c.execute('SELECT COUNT(*) FROM faults').fetchone()[0]} | RuleLogs {c.execute('SELECT COUNT(*) FROM rule_execution_log').fetchone()[0]}")
conn.close()
