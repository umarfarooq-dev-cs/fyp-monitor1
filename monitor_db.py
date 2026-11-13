# monitor_db.py - Database Monitor + Rule Engine (DB Version)
# Matched with: devices.py + schema-1.sql + seed-rules.sql + insert.py
# Checks: ICMP + HTTP + DNS + SNMP + Port Status
# Storage: Tiered - Detailed metrics only for faults, Hourly summary for normal
import subprocess
import sqlite3
import time
import sys
import socket
import urllib.request
import urllib.error
import re

DB = "network_monitor.db"
PING_COUNT = 3
PING_TIMEOUT = 2
CHECK_INTERVAL = 60

def ping_ip(ip):
    """Ping check - Returns icmp_status (1/0), latency_ms, packet_loss_percent."""
    try:
        r = subprocess.run(
            ["ping", "-c", str(PING_COUNT), "-W", str(PING_TIMEOUT), ip],
            capture_output=True, text=True, timeout=5
        )
        loss = 100.0
        latency = None
        up = 0

        # Parse packet loss
        for line in r.stdout.splitlines():
            if "packet loss" in line:
                m = re.search(r"(\d+)% packet loss", line)
                if m:
                    loss = float(m.group(1))
            if "rtt min/avg" in line or "round-trip" in line:
                try:
                    avg = line.split("=")[1].split("/")[1]
                    latency = float(avg)
                except:
                    latency = None

        if r.returncode == 0:
            up = 1
        else:
            up = 0
            latency = None
            loss = 100.0

        return up, latency, loss
    except Exception:
        return 0, None, 100.0

def check_http(ip):
    """HTTP check - Server only. Returns HTTP status code or 0 if no connection."""
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
    """DNS check - Returns 1 if DNS works, 0 if fails."""
    try:
        socket.gethostbyname("google.com")
        return 1
    except:
        return 0

def check_snmp_cpu(ip):
    """SNMP CPU check - Returns CPU percent or None if SNMP not available."""
    try:
        r = subprocess.run(
            ["snmpwalk", "-v2c", "-c", "public", "-t", "2", "-r", "1", ip, "1.3.6.1.2.1.25.3.3.1.2"],
            capture_output=True, text=True, timeout=3
        )
        if r.returncode == 0 and "INTEGER" in r.stdout:
            m = re.search(r"INTEGER:\s*(\d+)", r.stdout)
            if m:
                return float(m.group(1))
        return None
    except:
        return None

def get_rule_for_down(device_type):
    """Map device_type to correct rule for DOWN fault."""
    mapping = {
        "router": "R01",
        "core_switch": "R06",
        "server": "R07",
        "pc": "R08",
    }
    return mapping.get(device_type, "R01")

def get_rule_details(cursor, rule_id):
    """Get rule cause, action, verification from rules table."""
    cursor.execute(
        "SELECT rule_name, probable_cause, recommended_action, verification_step FROM rules WHERE rule_id = ?",
        (rule_id,)
    )
    row = cursor.fetchone()
    if row:
        return row
    return ("Unknown Rule", "Unknown cause", "Check device", "Ping device")

def log_rule_firing(cursor, rule_id, device_id, result, details):
    """Log rule execution to rule_firings table."""
    cursor.execute(
        "INSERT INTO rule_firings (rule_id, device_id, result, details) VALUES (?, ?, ?, ?)",
        (rule_id, device_id, result, details)
    )

def create_or_update_fault(cursor, device_id, rule_id, evidence, message, severity="Critical"):
    """
    Create fault only if no open fault exists for same device + rule.
    Prevents duplicate faults (R15).
    Returns True if new fault created.
    """
    cursor.execute(
        "SELECT fault_id FROM faults WHERE device_id = ? AND rule_id = ? AND status = 'open'",
        (device_id, rule_id)
    )
    existing = cursor.fetchone()
    if existing:
        # Fault already open, do not create duplicate
        return False

    cursor.execute(
        "INSERT INTO faults (device_id, rule_id, status, evidence) VALUES (?, ?, 'open', ?)",
        (device_id, rule_id, evidence)
    )
    # Also add to fault_history for dashboard alerts
    cursor.execute(
        "INSERT INTO fault_history (device_id, severity, message) VALUES (?, ?, ?)",
        (device_id, severity, message)
    )
    return True

def resolve_faults(cursor, device_id):
    """Resolve open faults when device comes back UP (R10)."""
    cursor.execute(
        "SELECT fault_id, rule_id FROM faults WHERE device_id = ? AND status = 'open'",
        (device_id,)
    )
    open_faults = cursor.fetchall()
    for fault_id, rule_id in open_faults:
        cursor.execute(
            "UPDATE faults SET status = 'resolved', resolved_at = CURRENT_TIMESTAMP WHERE fault_id = ?",
            (fault_id,)
        )
        cursor.execute(
            "INSERT INTO fault_history (device_id, severity, message) VALUES (?, 'Info', ?)",
            (device_id, f"Device recovered - Fault {rule_id} resolved (R10)")
        )
        log_rule_firing(cursor, "R10", device_id, "fired", "Device recovered, fault resolved")

def update_hourly_summary(cursor, device_id, up):
    """Update hourly summary - Tiered storage for normal data."""
    cursor.execute(
        """
        INSERT INTO metrics_hourly (device_id, hour_start, avg_latency_ms, max_packet_loss, up_count, down_count)
        VALUES (?, strftime('%Y-%m-%d %H:00:00', 'now'), NULL, NULL, ?, ?)
        ON CONFLICT(device_id, hour_start) DO UPDATE SET
            up_count = up_count + excluded.up_count,
            down_count = down_count + excluded.down_count
        """,
        (device_id, 1 if up == 1 else 0, 1 if up == 0 else 0)
    )

def main():
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    # Check DNS once per cycle
    dns_ok = check_dns()

    cur.execute("SELECT device_id, device_name, ip_address, device_type, vlan_id FROM devices")
    devices = cur.fetchall()
    print(f"\n--- Monitoring {len(devices)} targets | DNS: {'OK' if dns_ok else 'FAIL'} ---", flush=True)

    for device_id, name, ip, device_type, vlan_id in devices:
        up, latency, loss = ping_ip(ip)
        status = "UP" if up == 1 else "DOWN"

        # HTTP only for server
        http_status = None
        if device_type == "server":
            http_status = check_http(ip)

        # SNMP CPU only for router
        snmp_cpu = None
        if device_type == "router":
            snmp_cpu = check_snmp_cpu(ip)

        # Port status = same as ICMP for now (switch port check via ping)
        port_status = status
        interface_status = status

        print(f"{status} {name} [{ip}] latency={latency} loss={loss}% HTTP={http_status} CPU={snmp_cpu}", flush=True)

        # --- TIERED STORAGE ---
        # If DOWN or high loss/latency -> Save detailed metrics (for fault evidence)
        # If normal -> Save only hourly summary (saves 97% storage)
        is_fault = (up == 0) or (loss > 50) or (latency is not None and latency > 100) or (http_status == 0 and device_type == "server")

        if is_fault:
            cur.execute(
                """
                INSERT INTO metrics
                (device_id, icmp_status, latency_ms, packet_loss_percent, http_status, snmp_cpu_percent, interface_status, port_status, dns_status, ip_address_assigned)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (device_id, up, latency, loss, http_status, snmp_cpu, interface_status, port_status, dns_ok, ip)
            )
        else:
            update_hourly_summary(cur, device_id, up)

        # Update device status
        cur.execute(
            "UPDATE devices SET status = ? WHERE device_id = ?",
            (status, device_id)
        )

        # --- RULE ENGINE ---

        # R01 / R06 / R07 / R08 - Device DOWN - Power First
        if up == 0:
            rule_id = get_rule_for_down(device_type)
            rule_name, cause, action, verify = get_rule_details(cur, rule_id)
            evidence = f"Ping failed 3 times, Loss 100%, Latency None, Port {port_status}"
            message = f"[{rule_id}-Critical] {name} DOWN - {cause}. Action: {action}"
            created = create_or_update_fault(cur, device_id, rule_id, evidence, message, "Critical")
            if created:
                log_rule_firing(cur, rule_id, device_id, "fired", evidence)
                print(f"  -> FAULT CREATED: {rule_id} - {name} - {cause}", flush=True)
            else:
                log_rule_firing(cur, rule_id, device_id, "fired", "Fault already open, duplicate suppressed (R15)")

        # Device UP - Resolve open faults (R10)
        else:
            resolve_faults(cur, device_id)

            # R02 - High Packet Loss
            if loss > 50:
                evidence = f"Packet Loss {loss}% > 50% threshold"
                message = f"[R02-Warning] {name} High Packet Loss {loss}%"
                create_or_update_fault(cur, device_id, "R02", evidence, message, "Warning")
                log_rule_firing(cur, "R02", device_id, "fired", evidence)

            # R03 - High Latency
            if latency is not None and latency > 100:
                evidence = f"Latency {latency}ms > 100ms threshold"
                message = f"[R03-Warning] {name} High Latency {latency}ms"
                create_or_update_fault(cur, device_id, "R03", evidence, message, "Warning")
                log_rule_firing(cur, "R03", device_id, "fired", evidence)

            # R22 - Server Ping UP but HTTP DOWN
            if device_type == "server" and http_status == 0:
                evidence = f"Ping UP but HTTP 0 - Service down"
                message = f"[R22-Critical] {name} Ping UP but HTTP DOWN - Restart service"
                create_or_update_fault(cur, device_id, "R22", evidence, message, "Critical")
                log_rule_firing(cur, "R22", device_id, "fired", evidence)

            # R04 - Server HTTP Error (404, 500 etc)
            if device_type == "server" and http_status is not None and http_status != 0 and http_status != 200:
                evidence = f"HTTP Status {http_status} != 200"
                message = f"[R04-Critical] {name} HTTP Error {http_status}"
                create_or_update_fault(cur, device_id, "R04", evidence, message, "Critical")
                log_rule_firing(cur, "R04", device_id, "fired", evidence)

            # R19 - High CPU on Router
            if device_type == "router" and snmp_cpu is not None and snmp_cpu > 85:
                evidence = f"SNMP CPU {snmp_cpu}% > 85% threshold"
                message = f"[R19-Warning] {name} High CPU {snmp_cpu}%"
                create_or_update_fault(cur, device_id, "R19", evidence, message, "Warning")
                log_rule_firing(cur, "R19", device_id, "fired", evidence)

            # R17 - DNS Failure
            if dns_ok == 0:
                evidence = "Ping UP but DNS resolve failed"
                message = f"[R17-Critical] DNS Failure - Ping UP but name not resolving"
                create_or_update_fault(cur, device_id, "R17", evidence, message, "Critical")
                log_rule_firing(cur, "R17", device_id, "fired", evidence)

    conn.commit()
    conn.close()
    print(f"Saved monitoring cycle to {DB}", flush=True)

if __name__ == "__main__":
    if "--once" in sys.argv:
        main()
    else:
        while True:
            main()
            print("Waiting 60 seconds... Press Ctrl+C to stop", flush=True)
            time.sleep(CHECK_INTERVAL)
