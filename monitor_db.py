for dev in DEVICES:
    # FIX: Handle Device object (dev.ip) and dict (dev['ip']) both
    if isinstance(dev, dict):
        ip = dev.get('ip', '')
        dev_id = dev.get('id', 0)
        dev_type = dev.get('type', 'host')
        dev_name = dev.get('name', ip)
    else:
        # It's Device object from devices.py
        ip = getattr(dev, 'ip', '')
        dev_id = getattr(dev, 'id', 0)
        dev_type = getattr(dev, 'type', 'host')
        dev_name = getattr(dev, 'name', ip)

    # 1. ICMP - Existing
    up, lat = ping_ip(ip)
    icmp_status = 1 if up else 0
    packet_loss = 0 if up else 100

    # 2. NEW: TCP + HTTP only for Server (lightweight - not for all 9 devices)
    http_status = None
    tcp_status = None
    if dev_type == 'server' or '40.10' in ip or 'server' in dev_name.lower():
        tcp_status = check_tcp(ip, 80)
        http_status = check_http(ip, 80)

    # Insert into metrics - handles both old and new schema
    try:
        # Try new schema with http/tcp columns
        c.execute("""INSERT INTO metrics(device_id, timestamp, icmp_status, latency_ms, packet_loss, http_status, tcp_port_80_status)
                     VALUES (?,?,?,?,?,?,?)""",
                  (dev_id, datetime.datetime.now().isoformat(), icmp_status, lat, packet_loss, http_status, tcp_status))
    except sqlite3.OperationalError:
        # Fallback to old schema (only icmp columns) - if you haven't migrated yet
        c.execute("""INSERT INTO metrics(device_id, timestamp, icmp_status, latency_ms, packet_loss)
                     VALUES (?,?,?,?,?)""",
                  (dev_id, datetime.datetime.now().isoformat(), icmp_status, lat, packet_loss))

    print(f"{'UP' if up else 'DOWN'} {dev_name} {ip} {lat}ms TCP:{tcp_status} HTTP:{http_status}")
