# monitor_v2.py - FINAL - Fixed dns_ok Error
# Works with devices.py - 11 Targets
import subprocess
import socket
import time
import datetime
import sqlite3
import os

from devices import FLAT_TARGETS

DB_FILE = "network_monitor.db"

def ping_host(ip):
    """Ping 1 device, return (is_up, latency_ms, loss_percent)"""
    try:
        # Linux ping: -c 3 packets, -W 1 timeout
        out = subprocess.run(
            ["ping", "-c", "3", "-W", "1", ip],
            capture_output=True, text=True, timeout=5
        ).stdout

        if "0 received" in out or "100% packet loss" in out:
            return False, 0.0, 100.0

        # latency nikalna
        latency = 0.0
        loss = 0.0
        for line in out.splitlines():
            if "packet loss" in line:
                try:
                    loss = float(line.split("%")[0].split()[-1])
                except:
                    loss = 0.0
            if "rtt min/avg" in line or "round-trip" in line:
                try:
                    latency = float(line.split("=")[1].split("/")[1])
                except:
                    latency = 0.0
        return True, latency, loss
    except Exception:
        return False, 0.0, 100.0

def check_dns():
    """DNS check - google.com resolve hota hai ya nahi"""
    try:
        socket.gethostbyname("google.com")
        print("[DNS] google.com resolve: OK - For R17")
        return 1  # 1 = OK
    except Exception:
        print("[DNS] google.com resolve: FAIL")
        return 0  # 0 = FAIL

def check_http(ip):
    """Server ke liye HTTP check - port 80 open hai ya nahi"""
    try:
        s = socket.socket()
        s.settimeout(2)
        s.connect((ip, 80))
        s.close()
        return 0  # 0 = HTTP UP
    except Exception:
        return 1  # 1 = HTTP DOWN

def check_all():
    results = []
    for t in FLAT_TARGETS:
        ip = t.get("ip", t.get("ip_address", ""))
        name = t.get("device", t.get("name", "Unknown"))
        dtype = t.get("type", "host")

        is_up, latency, loss = ping_host(ip)
        status = "UP" if is_up else "DOWN"

        http_status = None
        if dtype == "server":
            http_status = check_http(ip)

        # Line 96 wali print - isi format me chahiye tha
        print(f"[{status}] {name} ({ip}) - {latency:.3f}ms Loss:{loss:.1f}% HTTP:{http_status} CPU:None")

        results.append({
            "device": name,
            "name": name,
            "ip": ip,
            "type": dtype,
            "status": status,
            "latency": latency,
            "loss": loss,
            "http": http_status,
            "interface": t.get("interface", ""),
        })
    return results

def correlate(results, dns_ok):
    """AUTO RULE ENGINE - 25 RULES ANALYSIS"""
    print("\n--- AUTO RULE ENGINE - 25 RULES ANALYSIS ---")

    down_devices = [r for r in results if r["status"] == "DOWN"]
    down_router = [r for r in down_devices if r["type"] == "router"]
    down_core = [r for r in down_devices if r["type"] == "core_switch"]

    # R08 - Host DOWN
    for r in down_devices:
        if r["type"] == "host":
            print(f"[R08-Warning] Host {r['device']} DOWN - {r['ip']}")
            print(f"ACTION: 1. Check PC POWER first, 2. If Power is ON, check Firewall / IP config")

    # R02 - Core Switch High Packet Loss
    for r in results:
        if r["type"] == "core_switch" and r["loss"] > 10:
            print(f"[R02-Critical] Core-Switch-{r['device']} High Packet Loss {r['loss']:.1f}%")

    # R22 - Server Ping UP but HTTP DOWN
    for r in results:
        if r["type"] == "server" and r["status"] == "UP" and r["http"] == 1:
            print(f"[R22-Critical] Server {r['device']} Ping UP but HTTP DOWN (HTTP=0)")
            print(f"ACTION: Server is ON, Service is DOWN - Restart Apache/Nginx")

    # --- YE LINE THI JISME dns_ok ERROR AA RAHA THA - AB FIX HAI ---
    # dns_ok ab function ko upar se mil raha hai, isliye NameError nahi aayega
    if dns_ok == 0 and len(down_router) == 0 and not down_core:
        print("[R17-Critical] DNS FAIL but Router & Core UP - Check DNS Server")

    if len(down_router) > 0:
        print("[R01-Critical] Router DOWN - All network may be DOWN")

    print(f"\nSUMMARY: Total={len(results)} UP={len(results)-len(down_devices)} DOWN={len(down_devices)}")

def save_to_db(results):
    """Results ko DB me save karna"""
    try:
        if not os.path.exists(DB_FILE):
            return
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        for r in results:
            cur.execute(
                "UPDATE devices SET status=? WHERE ip_address=? OR device_name=?",
                (r["status"], r["ip"], r["device"])
            )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB save skip: {e}")

if __name__ == "__main__":
    print(f"=== Monitoring Started {datetime.datetime.now()} ===")
    print(f"Targets: {len(FLAT_TARGETS)}")
    print()

    # dns_ok yahan define ho raha hai, phir correlate() ko bhej rahe hain
    dns_ok = check_dns()
    print()

    results = check_all()
    correlate(results, dns_ok)
    save_to_db(results)
    print("\n=== Monitoring Finished ===")
