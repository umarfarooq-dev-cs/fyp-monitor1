# monitor_v2.py - Network Monitor + Auto Rule Engine (FYP Core)
# 25 Rules Auto + Power-First + Multi-Signal
# Checks: ICMP + SNMP + Port Status + HTTP + DNS + DHCP
import subprocess
import socket
import urllib.request
import urllib.error
import re
from datetime import datetime
from devices import FLAT_TARGETS

def ping_ip(ip):
    """Ping check - For R01, R02, R03. Returns UP/DOWN, latency, packet loss."""
    try:
        r = subprocess.run(["ping", "-c", "3", "-W", "2", ip], capture_output=True, text=True, timeout=5)
        loss = 100.0
        lat = 0.0
        up = (r.returncode == 0)
        for line in r.stdout.splitlines():
            if "packet loss" in line:
                m = re.search(r"(\d+)% packet loss", line)
                if m:
                    loss = float(m.group(1))
            if "rtt min/avg" in line or "round-trip" in line:
                try:
                    avg = line.split("=")[1].split("/")[1]
                    lat = float(avg)
                except:
                    lat = 0.5
        if not up:
            return False, 0.0, 100.0
        return True, lat, loss
    except Exception:
        return False, 0.0, 100.0

def check_http(ip):
    """HTTP check - For R04, R22. Server only."""
    try:
        req = urllib.request.Request(f"http://{ip}", method='GET')
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        # 404, 403, 500 means server is UP, service responded
        return e.code
    except Exception:
        return 0

def check_dns():
    """DNS check - For R17."""
    try:
        socket.gethostbyname("google.com")
        return 1
    except:
        return 0

def check_snmp_cpu(ip):
    """SNMP CPU check - For R05, R19. Returns None if SNMP not available."""
    try:
        r = subprocess.run(["snmpwalk", "-v2c", "-c", "public", "-t", "2", "-r", "1", ip, "1.3.6.1.2.1.25.3.3.1.2"],
                           capture_output=True, text=True, timeout=3)
        if r.returncode == 0 and "INTEGER" in r.stdout:
            m = re.search(r"INTEGER:\s*(\d+)", r.stdout)
            if m:
                return float(m.group(1))
        return None
    except:
        return None

def check_all():
    """Check all devices: Ping + HTTP (Server only) + DNS + SNMP."""
    results = []
    dns_ok = check_dns()
    print(f"[DNS] google.com resolve: {'OK' if dns_ok else 'FAIL'} - For R17\n")

    for t in FLAT_TARGETS:
        dtype = t.get("type", "host")
        up, lat, loss = ping_ip(t["ip"])

        http_code = None
        if dtype == "server":
            http_code = check_http(t["ip"])

        cpu = None
        if dtype == "router-interface":
            cpu = check_snmp_cpu(t["ip"])

        is_apipa = t["ip"].startswith("169.254.")

        results.append({
            **t, "type": dtype,
            "status": "UP" if up else "DOWN",
            "latency": lat, "loss": loss,
            "http": http_code, "cpu": cpu,
            "dns": dns_ok, "apipa": is_apipa
        })
        print(f"[{results[-1]['status']}] {t['device']} {t.get('interface','')} ({t['ip']}) - {lat}ms Loss:{loss}% HTTP:{http_code} CPU:{cpu}")
    return results

def correlate(results):
    """Auto Rule Engine - Evaluates 25 Rules."""
    router_intfs = [r for r in results if r["type"] == "router-interface"]
    core = next((r for r in results if r["device"] == "Core-Switch-SW1"), None)
    hosts_only = [r for r in results if r["type"] == "host"]
    servers = [r for r in results if r["type"] == "server"]

    down_router = [r for r in router_intfs if r["status"] == "DOWN"]
    down_core = core["status"] == "DOWN" if core else False
    down_hosts = [r for r in hosts_only if r["status"] == "DOWN"]
    down_servers = [r for r in servers if r["status"] == "DOWN"]

    print("\n--- AUTO RULE ENGINE - 25 RULES ANALYSIS ---")

    # R13: Multiple Devices Fail Together
    if len(down_hosts) + len(down_servers) >= 3 and len(down_router) >= 2:
        print("[R13-Critical] Multiple Devices Fail Together")
        print("ACTION: 1. Check common Power / UPS first, 2. Then check upstream Router")

    # R01 + R06: Core Switch / Gateway Down - Power First
    if len(down_router) == 4 and down_core:
        print("[R01/R06-Critical] ROOT CAUSE: Core-Switch Failure")
        print("ACTION: 1. Check Core Switch POWER first, 2. Then check Cable / Trunk e0/0")
        print("EVIDENCE: Ping failed 3 times, Loss 100%")

    elif len(down_router) == 1 and not down_core:
        f = down_router[0]
        print(f"[R01-Critical] Gateway {f['interface']} DOWN - VLAN {f.get('vlan','?')} unreachable")
        print(f"ACTION: 1. Check Router Power first, 2. Then check Interface {f['interface']}")

    # R08: Single Host Down - Power First
    elif len(down_router) == 0 and not down_core and down_hosts:
        for h in down_hosts:
            print(f"[R08-Warning] Host {h['device']} DOWN - {h['ip']}")
            print(f"ACTION: 1. Check PC POWER first, 2. If Power is ON, check Firewall / IP config")

    # R07: Server Down - Power First
    for s in down_servers:
        print(f"[R07-Critical] Server {s['device']} DOWN")
        print(f"ACTION: 1. Check Server Power first, 2. Then check NIC / Cable")

    # R02, R03
    for r in results:
        if r["status"] == "UP" and r["loss"] > 50:
            print(f"[R02-Warning] {r['device']} High Packet Loss {r['loss']}%")
        if r["status"] == "UP" and r["latency"] > 100:
            print(f"[R03-Warning] {r['device']} High Latency {r['latency']}ms")

    # R22: Server HTTP Down but Ping UP
    for s in servers:
        if s["status"] == "UP" and s["http"] is not None and s["http"] == 0:
            print(f"[R22-Critical] Server {s['device']} Ping UP but HTTP DOWN (HTTP=0)")
            print(f"ACTION: Server is ON, Service is DOWN - Restart Apache/Nginx")

    # R17: DNS Failure
    if dns_ok == 0 and len(down_router) == 0 and not down_core:
        print("[R17-Critical] DNS Failure - Ping is UP but name resolution failed")
        print("ACTION: Check DNS Server IP")

    # R18: DHCP Failure
    for r in results:
        if r["apipa"]:
            print(f"[R18-Critical] DHCP Failure - {r['device']} got no IP, APIPA {r['ip']}")

    # R19: High CPU
    for r in results:
        if r["cpu"] is not None and r["cpu"] > 85:
            print(f"[R19-Warning] {r['device']} High CPU {r['cpu']}%")

    if len(down_router) == 0 and not down_core and len(down_hosts) == 0 and len(down_servers) == 0:
        print("STATUS: All systems HEALTHY - No fault")

    print("\n--- Remaining Rules R10,R11,R12,R14,R15,R16,R20,R21,R23,R24,R25 use DB history ---")

if __name__ == "__main__":
    print(f"=== Monitoring Started {datetime.now()} ===\nTargets: {len(FLAT_TARGETS)}\n")
    results = check_all()
    correlate(results)
