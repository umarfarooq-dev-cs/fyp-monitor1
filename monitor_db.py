import subprocess, sqlite3, time, sys

DB = "database.db"

def ping_ip(ip):
    try:
        r = subprocess.run(
            ["ping", "-c", "1", "-W", "1", ip],
            capture_output=True, text=True, timeout=3
        )
        if r.returncode != 0:
            return 0, None, 100.0
        latency = None
        for line in r.stdout.splitlines():
            if "time=" in line:
                try:
                    latency = float(line.split("time=")[1].split()[0])
                except:
                    pass
        return 1, latency, 0.0
    except:
        return 0, None, 100.0

def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT device_id, device_name, ip_address FROM devices")
    devices = cur.fetchall()
    print(f"\n--- Monitoring {len(devices)} targets ---", flush=True)

    for device_id, name, ip in devices:
        up, latency, loss = ping_ip(ip)
        status = "UP" if up == 1 else "DOWN"
        print(f"{status} {name} [{ip}] latency={latency}", flush=True)

        cur.execute(
            "INSERT INTO metrics (device_id, icmp_status, latency_ms, packet_loss_percent, interface_status) VALUES (?, ?, ?, ?, ?)",
            (device_id, up, latency, loss, status)
        )
        cur.execute(
            "UPDATE devices SET status=? WHERE device_id=?",
            (status, device_id)
        )

        # If DOWN, create fault with YOUR table's real columns
        if up == 0:
            cur.execute(
                "INSERT INTO faults (device_id, rule_id, status, evidence) VALUES (?, 'R01', 'open', 'Ping failed')",
                (device_id,)
            )

    conn.commit()
    conn.close()
    print(f"Saved {len(devices)} rows to {DB}", flush=True)

if __name__ == "__main__":
    if "--once" in sys.argv:
        main()
    else:
        while True:
            main()
            print("Waiting 60 seconds... Press Ctrl+C to stop", flush=True)
            time.sleep(60)
