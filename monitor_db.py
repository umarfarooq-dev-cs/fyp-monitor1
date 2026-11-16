import subprocess
import sqlite3
import time
import os
from datetime import datetime

DB_FILE = "database.db"

# Single entry for Router and Core-Switch
# Router has 4 gateway IPs (.1 in each VLAN) but it is one physical device,
# so we monitor it once using 192.168.40.1
# Core-Switch has 4 SVI IPs (.2 in each VLAN) but it is one physical device,
# so we monitor it once using 192.168.40.2

TARGETS = [
    {"name": "Main-Router", "ip": "192.168.40.1", "type": "router"},
    {"name": "Core-Switch", "ip": "192.168.40.2", "type": "switch"},
    {"name": "Admin-PC", "ip": "192.168.10.11", "type": "pc"},
    {"name": "Lab-PC", "ip": "192.168.20.11", "type": "pc"},
    {"name": "Library-PC", "ip": "192.168.30.11", "type": "pc"},
    {"name": "Server-PC", "ip": "192.168.40.11", "type": "server"},
]

def ping_target(ip, count=3):
    try:
        result = subprocess.run(
            ["ping", "-c", str(count), "-W", "2", ip],
            capture_output=True, text=True, timeout=10
        )
        output = result.stdout
        if "0 received" in output or "100% packet loss" in output:
            return "DOWN", 0.0, 100.0
        latency = 0.0
        for line in output.splitlines():
            if "rtt min/avg" in line:
                # rtt min/avg/max/mdev = 1.669/3.577/7.166/2.539 ms
                parts = line.split("=")[1].strip().split("/")
                latency = float(parts[1])
                break
        loss = 0.0
        for line in output.splitlines():
            if "packet loss" in line:
                loss = float(line.split("%")[0].split()[-1])
                break
        return "UP", latency, loss
    except Exception:
        return "DOWN", 0.0, 100.0

def check_dns():
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "2", "8.8.8.8"],
            capture_output=True, text=True, timeout=5
        )
        return "OK" if result.returncode == 0 else "FAIL"
    except Exception:
        return "FAIL"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS monitoring (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            device_name TEXT,
            ip TEXT,
            status TEXT,
            latency REAL,
            loss REAL
        )
    """)
    conn.commit()
    conn.close()

def save_to_db(results):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for r in results:
        cur.execute(
            "INSERT INTO monitoring (timestamp, device_name, ip, status, latency, loss) VALUES (?, ?, ?, ?, ?, ?)",
            (timestamp, r["name"], r["ip"], r["status"], r["latency"], r["loss"])
        )
    conn.commit()
    conn.close()

def main():
    init_db()
    print(f"--- Monitoring {len(TARGETS)} targets | DNS: {check_dns()} ---")
    while True:
        results = []
        for target in TARGETS:
            status, latency, loss = ping_target(target["ip"])
            results.append({
                "name": target["name"],
                "ip": target["ip"],
                "status": status,
                "latency": latency,
                "loss": loss
            })
            print(f"{status} {target['name']} [{target['ip']}] latency={latency} loss={loss}%")
        save_to_db(results)
        print(f"Saved monitoring cycle to {DB_FILE}")
        print("Waiting 60 seconds... Press Ctrl+C to stop")
        time.sleep(60)

if __name__ == "__main__":
    main()
