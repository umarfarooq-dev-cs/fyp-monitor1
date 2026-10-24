# monitor_v2.py - Network Monitor + Rule Engine (FYP Core)
# This pings all devices and finds ROOT CAUSE

import subprocess  # To run ping command
from datetime import datetime
from devices import FLAT_TARGETS  # Import IPs from devices.py (FILE 1)

def ping_ip(ip):
    """Ping one IP and return UP/DOWN + latency"""
    try:
        # Run Linux ping command: ping -c 1 -W 2 192.168.10.1
        r = subprocess.run(["ping","-c","1","-W","2",ip], capture_output=True, text=True, timeout=3)
        if r.returncode == 0:  # 0 means ping success
            for line in r.stdout.splitlines():
                if "time=" in line:  # Extract time=0.5ms
                    return True, float(line.split("time=")[1].split()[0])
            return True, 0.5  # UP but no time found
        else:
            return False, 0   # DOWN
    except:
        return False, 0

def check_all():
    """Ping all devices from FLAT_TARGETS"""
    results = []
    for t in FLAT_TARGETS:
        up, lat = ping_ip(t["ip"])
        results.append({**t, "status": "UP" if up else "DOWN", "latency": lat})
        # Print live status
        print(f"[{results[-1]['status']}] {t['device']} {t['interface']} ({t['ip']}) - {lat}ms")
    return results

def correlate(results):
    """
    RULE ENGINE - This is your FYP innovation!
    Finds ROOT CAUSE instead of just showing DOWN devices
    """
    router_intfs = [r for r in results if r["type"] == "router-interface"]
    core = next((r for r in results if r["device"] == "Core-Switch-SW1"), None)
    hosts = [r for r in results if r["type"] in ("host","server")]

    down_router = [r for r in router_intfs if r["status"] == "DOWN"]
    down_core = core["status"] == "DOWN" if core else False
    down_hosts = [r for r in hosts if r["status"] == "DOWN"]

    print("\n--- RULE ENGINE ANALYSIS ---")
    # RULE 1: If all 4 router gateways + core down = Core Switch failed
    if len(down_router) == 4 and down_core:
        print("ROOT CAUSE: Core-Switch Failure")
        print("REASON: All 4 Router gateways + Core unreachable")
        print("ACTION: Check Core Switch power, trunk e0/0")
    # RULE 2: If only 1 gateway down = That specific interface down
    elif len(down_router) == 1 and not down_core:
        f = down_router[0]
        print(f"ROOT CAUSE: Router Interface {f['interface']} DOWN")
        print(f"REASON: Only VLAN {f['vlan']} unreachable")
        print(f"ACTION: Check Router: interface {f['interface']}")
    # RULE 3: If gateways UP but host DOWN = Host problem
    elif len(down_router) == 0 and not down_core and down_hosts:
        for h in down_hosts:
            print(f"ROOT CAUSE: Host {h['device']} DOWN - Check host {h['ip']}")
    # RULE 4: All UP = Healthy
    elif len(down_router) == 0 and not down_core and len(down_hosts) == 0:
        print("STATUS: All systems HEALTHY - No fault")
    else:
        print(f"PARTIAL FAILURE: {len(down_router)} router interfaces down, core {'DOWN' if down_core else 'UP'}")

if __name__ == "__main__":
    print(f"=== Monitoring Started {datetime.now()} ===\nTargets: {len(FLAT_TARGETS)}\n")
    results = check_all()
    correlate(results)
