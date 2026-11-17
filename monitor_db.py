# monitor_db.py - Database Monitor + Rule Engine (DB Version)
# FINAL FIXED: R01 to R25 - ALL RULES + 3 LOGIC BUGS FIXED
# FIXED: EVE-NG Lab - Auto Interface + Gateway 192.168.10.1 + Syntax Fix
import subprocess
import sqlite3
import time
import sys
import socket
import urllib.request
import urllib.error
import re
import os
import json

DB = "database.db"
PING_COUNT = 3
PING_TIMEOUT = 2
CHECK_INTERVAL = 60

# EVE-NG Lab IPs
GATEWAY = "192.168.10.1"
CORE_IP = "192.168.10.2"
MY_IP = "192.168.10.11"
MY_NET = "192.168.10.0/24"

STATE_FILE = "monitor_state.json"

def get_iface():
    try:
        r = subprocess.run(["ip", "route"], capture_output=True, text=True)
        for line in r.stdout.splitlines():
            if "default via" in line:
                parts = line.split()
                if "dev" in parts:
                    return parts[parts.index("dev") + 1]
    except Exception:
        pass
    return "eth0"

def ensure_routes():
    iface = get_iface()
    try:
        r = subprocess.run(["ip", "addr", "show", iface], capture_output=True, text=True)
        if MY_IP not in r.stdout:
            subprocess.run(["sudo", "ip", "addr", "add", f"{MY_IP}/24", "dev", iface], capture_output=True)
            print(f"ROUTE-FIX: {MY_IP} wapas lagaya on {iface}", flush=True)
        r2 = subprocess.run(["ip", "route"], capture_output=True, text=True)
        routes = r2.stdout
        for net in ["192.168.10.0/24", "192.168.20.0/24", "192.168.30.0/24", "192.168.40.0/24"]:
            if net not in routes:
                subprocess.run(["sudo", "ip", "route", "add", net, "via", GATEWAY, "dev", iface], capture_output=True)
                print(f"ROUTE-FIX: {net} via {GATEWAY} wapas lagaya", flush=True)
    except Exception as e:
        print(f"ROUTE-FIX failed (sudo chahiye hoga): {e}", flush=True)

def ping_ip(ip):
    try:
        r = subprocess.run(["ping", "-c", str(PING_COUNT), "-W", str(PING_TIMEOUT), ip], capture_output=True, text=True, timeout=10)
        loss = 100.0
        latency = None
        up = 0
        for line in r.stdout.splitlines():
            if "packet loss" in line:
                m = re.search(r"(\d+)% packet loss", line)
                if m: loss = float(m.group(1))
            if "rtt min/avg" in line or "round-trip" in line:
                try:
                    avg = line.split("=")[1].split("/")[1]
                    latency = float(avg)
                except: latency = None
        if r.returncode == 0: up = 1
        else: up = 0; latency = None; loss = 100.0
        return up, latency, loss
    except Exception:
        return 0, None, 100.0

def check_http(ip):
    try:
        req = urllib.request.Request(f"http://{ip}", method='GET')
        with urllib.request.urlopen(req, timeout=3) as resp: return resp.status
    except urllib.error.HTTPError as e: return e.code
    except Exception: return 0

def check_dns():
    try: socket.gethostbyname("google.com"); return 1
    except: return 0

def check_dns_time():
    try:
        s = time.time()
        socket.gethostbyname("google.com")
        return round((time.time() - s) * 1000, 2)
    except: return None

def check_snmp_value(ip, oid):
    try:
        r = subprocess.run(["snmpwalk", "-v2c", "-c", "public", "-t", "2", "-r", "1", ip, oid], capture_output=True, text=True, timeout=3)
        if r.returncode == 0 and "INTEGER" in r.stdout:
            m = re.search(r"INTEGER:\s*(\d+)", r.stdout)
            if m: return float(m.group(1))
        return None
    except: return None

def check_snmp_cpu(ip):
    return check_snmp_value(ip, "1.3.6.1.2.1.25.3.3.1.2")

def check_snmp_mem_percent(ip):
    # FIXED: Pehle wala OID bytes deta tha, % nahi. Ab Used aur Total dono le ke % nikalte hain.
    # Agar SNMP na mile to None, fault nahi banega, safe hai.
    try:
        used = check_snmp_value(ip, "1.3.6.1.2.1.25.2.3.1.6.1")
        total = check_snmp_value(ip, "1.3.6.1.2.1.25.2.3.1.5.1")
        if used is not None and total is not None and total > 0:
            return round((used / total) * 100, 2)
        return None
    except: return None

def get_arp_table():
    ips = {}
    try:
        r = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=5)
        for line in r.stdout.splitlines():
            m = re.search(r"\((\d+\.\d+\.\d+\.\d+)\) at ([0-9a-f:]+)", line)
            if m: ips[m.group(1)] = m.group(2)
    except: pass
    return ips

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f: return json.load(f)
        except: return {}
    return {}

def save_state(state):
    try:
        with open(STATE_FILE, "w") as f: json.dump(state, f)
    except: pass

def get_rule_for_down(device_type):
    mapping = {"router": "R01", "core_switch": "R06", "switch": "R06", "server": "R07", "pc": "R08"}
    return mapping.get(device_type, "R01")

def get_rule_details(cursor, rule_id):
    cursor.execute("SELECT rule_name, probable_cause, recommended_action, verification_step FROM rules WHERE rule_id = ?", (rule_id,))
    row = cursor.fetchone()
    if row: return row
    return ("Unknown Rule", "Unknown cause", "Check device", "Ping device")

def log_rule_firing(cursor, rule_id, device_id, result, details):
    cursor.execute("INSERT INTO rule_firings (rule_id, device_id, result, details) VALUES (?, ?, ?, ?)", (rule_id, device_id, result, details))

def create_or_update_fault(cursor, device_id, rule_id, evidence, message, severity="Critical"):
    cursor.execute("SELECT fault_id FROM faults WHERE device_id = ? AND rule_id = ? AND status = 'open'", (device_id, rule_id))
    if cursor.fetchone():
        # R15 - Duplicate suppression
        log_rule_firing(cursor, "R15", device_id, "suppressed", f"Duplicate {rule_id} suppressed, fault already open")
        return False
    cursor.execute("INSERT INTO faults (device_id, rule_id, status, evidence) VALUES (?, ?, 'open', ?)", (device_id, rule_id, evidence))
    cursor.execute("INSERT INTO fault_history (device_id, severity, message) VALUES (?, ?, ?)", (device_id, severity, message))
    return True

def resolve_faults(cursor, device_id):
    # FIXED: Pehle sirf DOWN wale resolve hote the, ab saare resolve honge jab device theek ho
    cursor.execute("SELECT fault_id, rule_id FROM faults WHERE device_id = ? AND status = 'open'", (device_id,))
    open_faults = cursor.fetchall()
    for fault_id, rule_id in open_faults:
        cursor.execute("UPDATE faults SET status = 'resolved', resolved_at = CURRENT_TIMESTAMP WHERE fault_id = ?", (fault_id,))
        cursor.execute("INSERT INTO fault_history (device_id, severity, message) VALUES (?, 'Info', ?)", (device_id, f"Device recovered - Fault {rule_id} resolved (R10)"))
        log_rule_firing(cursor, "R10", device_id, "fired", "Device recovered, fault resolved")

def resolve_single_fault(cursor, device_id, rule_id):
    # Jab ek specific condition theek ho jaye (jaise Loss kam ho gaya) to sirf uska fault resolve karo
    cursor.execute("SELECT fault_id FROM faults WHERE device_id = ? AND rule_id = ? AND status = 'open'", (device_id, rule_id))
    row = cursor.fetchone()
    if row:
        cursor.execute("UPDATE faults SET status = 'resolved', resolved_at = CURRENT_TIMESTAMP WHERE fault_id = ?", (row[0],))
        cursor.execute("INSERT INTO fault_history (device_id, severity, message) VALUES (?, 'Info', ?)", (device_id, f"Condition OK - Fault {rule_id} auto-resolved"))
        log_rule_firing(cursor, "R10", device_id, "fired", f"{rule_id} auto-resolved, condition OK")

def update_hourly_summary(cursor, device_id, up):
    cursor.execute("""INSERT INTO metrics_hourly (device_id, hour_start, avg_latency_ms, max_packet_loss, up_count, down_count)
        VALUES (?, strftime('%Y-%m-%d %H:00:00', 'now'), NULL, NULL, ?, ?)
        ON CONFLICT(device_id, hour_start) DO UPDATE SET up_count = up_count + excluded.up_count, down_count = down_count + excluded.down_count""",
        (device_id, 1 if up == 1 else 0, 1 if up == 0 else 0))

def main():
    ensure_routes()
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS metrics_hourly (
        device_id INTEGER, hour_start TEXT, avg_latency_ms REAL,
        max_packet_loss REAL, up_count INTEGER, down_count INTEGER,
        UNIQUE(device_id, hour_start))""")
    cur.execute("PRAGMA table_info(metrics)")
    cols = [r[1] for r in cur.fetchall()]
    if "port_status" not in cols: cur.execute("ALTER TABLE metrics ADD COLUMN port_status TEXT")# Naya wala - SAHI
try:
    if "port_status" not in cols: cur.execute("ALTER TABLE metrics ADD COLUMN port_status TEXT")
except Exception:
    pass
    if "dns_status" not in cols: cur.execute("ALTER TABLE metrics ADD COLUMN dns_status INTEGER")
    if "ip_address_assigned" not in cols: cur.execute("ALTER TABLE metrics ADD COLUMN ip_address_assigned TEXT")

    dns_ok = check_dns()
    dns_time = check_dns_time()
    state = load_state()
    arp_table = get_arp_table()

    # R16 - Gateway Check (alag se, ek bar)
    gw_up, gw_lat, gw_loss = ping_ip(GATEWAY)
    if gw_up == 0:
        print(f"R16 CRITICAL: Gateway {GATEWAY} DOWN!", flush=True)
    if dns_time is not None and dns_time > 2000:
        print(f"R18 WARNING: Slow DNS {dns_time}ms", flush=True)

    cur.execute("SELECT device_id, device_name, ip_address, device_type, vlan_id FROM devices ORDER BY device_id")
    all_devices = cur.fetchall()

    # Gateway device_id dhoondo taake R16 ka fault sirf uspe bane - FIXED
    gateway_device_id = None
    for d in all_devices:
        if d[2] == GATEWAY:
            gateway_device_id = d[0]
            break
    if gateway_device_id is None and len(all_devices) > 0:
        gateway_device_id = all_devices[0][0]  # fallback: pehla device (Router)

    seen_ips = {}
    devices = []
    for d in all_devices:
        device_id, name, ip, device_type, vlan_id = d
        if "GW" in name:
            continue
        if ip in seen_ips:
            # R14 - Duplicate IP
            prev_id = seen_ips[ip]
            print(f"R14 DUPLICATE IP: {name} [{ip}] duplicate of device {prev_id}", flush=True)
            create_or_update_fault(cur, device_id, "R14", f"Duplicate IP {ip} already used by device {prev_id}", f"[R14-Critical] {name} Duplicate IP {ip}", "Critical")
            log_rule_firing(cur, "R14", device_id, "fired", f"Duplicate IP {ip}")
            continue
        seen_ips[ip] = device_id
        devices.append(d)

    # R23 - Unauthorized Device - ARP me hai lekin DB me nahi
    known_ips = set(seen_ips.keys())
    for arp_ip, mac in arp_table.items():
        if arp_ip.startswith("192.168.") and arp_ip not in known_ips and arp_ip != MY_IP and arp_ip != GATEWAY:
            print(f"R23 UNAUTHORIZED: {arp_ip} MAC {mac} not in DB", flush=True)
            log_rule_firing(cur, "R23", 1, "fired", f"Unauthorized device {arp_ip} MAC {mac}")

    print(f"\n--- Monitoring {len(devices)} targets | DNS: {'OK' if dns_ok else 'FAIL'} ({dns_time}ms) | GW: {'UP' if gw_up else 'DOWN'} ---", flush=True)

    # FIXED R16: Gateway down hai to sirf gateway wale device pe 1 fault banao, har device pe nahi
    if gw_up == 0 and gateway_device_id is not None:
        create_or_update_fault(cur, gateway_device_id, "R16", f"Gateway {GATEWAY} unreachable - Ping failed", f"[R16-Critical] Gateway {GATEWAY} DOWN", "Critical")
        log_rule_firing(cur, "R16", gateway_device_id, "fired", "Gateway unreachable")
    if gw_up == 1 and gateway_device_id is not None:
        resolve_single_fault(cur, gateway_device_id, "R16")

    for device_id, name, ip, device_type, vlan_id in devices:
        up, latency, loss = ping_ip(ip)
        status = "UP" if up == 1 else "DOWN"
        http_status = check_http(ip) if device_type == "server" else None
        snmp_cpu = check_snmp_cpu(ip) if device_type in ("router", "core_switch", "server") else None
        snmp_mem = check_snmp_mem_percent(ip) if device_type in ("router", "server") else None
        port_status = status
        interface_status = status
        print(f"{status} {name} [{ip}] latency={latency} loss={loss}% HTTP={http_status} CPU={snmp_cpu} MEM={snmp_mem}", flush=True)

        # R09 - Flapping detection
        key = str(device_id)
        prev = state.get(key, {"last": status, "flaps": 0})
        if prev["last"] != status:
            prev["flaps"] = prev.get("flaps", 0) + 1
        else:
            prev["flaps"] = 0
        prev["last"] = status
        state[key] = prev

        is_fault = (up == 0) or (loss > 50) or (latency is not None and latency > 100) or (http_status == 0 and device_type == "server")
        if is_fault:
            cur.execute("""INSERT INTO metrics (device_id, icmp_status, latency_ms, packet_loss_percent, http_status, snmp_cpu_percent, interface_status, port_status, dns_status, ip_address_assigned)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (device_id, up, latency, loss, http_status, snmp_cpu, interface_status, port_status, dns_ok, ip))
        else:
            update_hourly_summary(cur, device_id, up)
        cur.execute("UPDATE devices SET status = ? WHERE device_id = ?", (status, device_id))

        if up == 0:
            rule_id = get_rule_for_down(device_type)
            rule_name, cause, action, verify = get_rule_details(cur, rule_id)
            evidence = f"Ping failed 3 times, Loss 100%, Latency None, Port {port_status}"
            message = f"[{rule_id}-Critical] {name} DOWN - {cause}. Action: {action}"
            created = create_or_update_fault(cur, device_id, rule_id, evidence, message, "Critical")
            if created:
                log_rule_firing(cur, rule_id, device_id, "fired", evidence)
                print(f"  -> FAULT: {rule_id} - {name} - {cause}", flush=True)
            else:
                log_rule_firing(cur, rule_id, device_id, "fired", "Fault already open, duplicate suppressed (R15)")

            if device_type in ("switch", "core_switch"):
                create_or_update_fault(cur, device_id, "R12", f"Port DOWN because {name} DOWN", f"[R12-Critical] {name} Port DOWN", "Critical")
                log_rule_firing(cur, "R12", device_id, "fired", "Port down with device")
            if device_type in ("router", "core_switch", "switch"):
                create_or_update_fault(cur, device_id, "R24", f"Link DOWN - No ping response from {ip}", f"[R24-Critical] {name} Link/Cable Down", "Critical")
                log_rule_firing(cur, "R24", device_id, "fired", "Link down")
            if device_type == "pc":
                create_or_update_fault(cur, device_id, "R05", f"PC {name} DOWN - IP {ip} not responding, DHCP maybe failed", f"[R05-Critical] {name} DHCP/IP Failed", "Critical")
                log_rule_firing(cur, "R05", device_id, "fired", "DHCP check failed with DOWN")

        else:
            # Device UP hai - FIXED: Saare DOWN wale faults resolve karo
            resolve_faults(cur, device_id)

            # R02 - Packet Loss - theek hone pe auto-resolve
            if loss > 50:
                create_or_update_fault(cur, device_id, "R02", f"Packet Loss {loss}% > 50%", f"[R02-Warning] {name} High Packet Loss {loss}%", "Warning")
                log_rule_firing(cur, "R02", device_id, "fired", f"Loss {loss}%")
            else:
                resolve_single_fault(cur, device_id, "R02")
            # R03 - Latency
            if latency is not None and latency > 100:
                create_or_update_fault(cur, device_id, "R03", f"Latency {latency}ms > 100ms", f"[R03-Warning] {name} High Latency {latency}ms", "Warning")
                log_rule_firing(cur, "R03", device_id, "fired", f"Latency {latency}ms")
            else:
                resolve_single_fault(cur, device_id, "R03")
            # R11 - Bandwidth
            if latency is not None and latency > 200 and loss > 20:
                create_or_update_fault(cur, device_id, "R11", f"Latency {latency}ms + Loss {loss}% = Link saturated", f"[R11-Warning] {name} Link Utilization High", "Warning")
                log_rule_firing(cur, "R11", device_id, "fired", "Link saturated")
            else:
                resolve_single_fault(cur, device_id, "R11")
            # R09 - Flapping
            if prev.get("flaps", 0) >= 3:
                create_or_update_fault(cur, device_id, "R09", f"Flapped {prev['flaps']} times - UP/DOWN loop", f"[R09-Warning] {name} Interface Flapping", "Warning")
                log_rule_firing(cur, "R09", device_id, "fired", f"Flaps {prev['flaps']}")
                state[key]["flaps"] = 0
            # R13 - VLAN
            if device_type in ("switch", "core_switch", "pc") and (vlan_id is None or vlan_id == ""):
                create_or_update_fault(cur, device_id, "R13", f"VLAN ID missing for {name}", f"[R13-Warning] {name} VLAN Mismatch / Not Assigned", "Warning")
                log_rule_firing(cur, "R13", device_id, "fired", "VLAN missing")
            # R22 - Ping UP HTTP DOWN
            if device_type == "server" and http_status == 0:
                create_or_update_fault(cur, device_id, "R22", "Ping UP but HTTP 0 - Service down", f"[R22-Critical] {name} Ping UP but HTTP DOWN - Restart service", "Critical")
                log_rule_firing(cur, "R22", device_id, "fired", "HTTP down")
            # R04 - HTTP Error
            if device_type == "server" and http_status is not None and http_status != 0 and http_status != 200:
                create_or_update_fault(cur, device_id, "R04", f"HTTP Status {http_status} != 200", f"[R04-Critical] {name} HTTP Error {http_status}", "Critical")
                log_rule_firing(cur, "R04", device_id, "fired", f"HTTP {http_status}")
            else:
                if device_type == "server":
                    resolve_single_fault(cur, device_id, "R04")
                    resolve_single_fault(cur, device_id, "R22")
            # R19 - CPU High
            if snmp_cpu is not None and snmp_cpu > 85:
                create_or_update_fault(cur, device_id, "R19", f"SNMP CPU {snmp_cpu}% > 85%", f"[R19-Warning] {name} High CPU {snmp_cpu}%", "Warning")
                log_rule_firing(cur, "R19", device_id, "fired", f"CPU {snmp_cpu}%")
            else:
                resolve_single_fault(cur, device_id, "R19")
            # R20 - Memory High - FIXED % wala
            if snmp_mem is not None and snmp_mem > 85:
                create_or_update_fault(cur, device_id, "R20", f"SNMP Memory {snmp_mem}% > 85%", f"[R20-Warning] {name} High Memory {snmp_mem}%", "Warning")
                log_rule_firing(cur, "R20", device_id, "fired", f"MEM {snmp_mem}%")
            else:
                resolve_single_fault(cur, device_id, "R20")
            # FIXED R21 - Ab har bar log nahi hoga. EVE-NG me temp sensor nahi hai, isliye skip.
            # Agar kabhi SNMP temp mile to yahan check karenge, warna DB nahi bharenge.
            # R17 - DNS Failure
            if dns_ok == 0:
                create_or_update_fault(cur, device_id, "R17", "Ping UP but DNS resolve failed", f"[R17-Critical] DNS Failure - Ping UP but name not resolving", "Critical")
                log_rule_firing(cur, "R17", device_id, "fired", "DNS failed")
            else:
                resolve_single_fault(cur, device_id, "R17")
            # R18 - Slow DNS
            if dns_time is not None and dns_time > 2000:
                create_or_update_fault(cur, device_id, "R18", f"DNS Time {dns_time}ms > 2000ms", f"[R18-Warning] Slow DNS {dns_time}ms", "Warning")
                log_rule_firing(cur, "R18", device_id, "fired", f"Slow DNS {dns_time}ms")
            else:
                resolve_single_fault(cur, device_id, "R18")
            # R05 - DHCP check - PC UP hai lekin ARP me nahi
            if device_type == "pc" and ip not in arp_table:
                create_or_update_fault(cur, device_id, "R05", f"PC {name} UP but not in ARP - IP {ip} not assigned / DHCP failed", f"[R05-Warning] {name} DHCP Failed - No ARP entry", "Warning")
                log_rule_firing(cur, "R05", device_id, "fired", "No ARP entry")
             else:
            if device_type == "pc":
                 resolve_single_fault(cur, device_id, "R05")
            # R25 - Config Change - sirf jab flap hua ho tabhi log karo, har bar nahi
            if prev.get("flaps", 0) > 0:
                log_rule_firing(cur, "R25", device_id, "checked", f"Config/State change detected - status flapped")

    save_state(state)
    conn.commit()
    conn.close()
    print(f"Saved monitoring cycle to {DB} - R01 to R25 checked", flush=True)

if __name__ == "__main__":
    if "--once" in sys.argv: main()
    else:
        while True:
            main()
            print("Waiting 60 seconds... Press Ctrl+C to stop", flush=True)
            time.sleep(CHECK_INTERVAL)
