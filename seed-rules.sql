-- ==========================================================
-- 15 Explainable Rules - All Implementable with Python Ping
-- Format matches teacher requirement Page 4
-- ==========================================================

INSERT INTO rules (rule_id, rule_name, predicate, time_window_seconds, persistence_count, severity, category, probable_cause, recommended_action, verification_step, enabled) VALUES
-- R01 to R09 = Your existing 9 rules (improved format)
('R01', 'Gateway Unreachable', 'icmp_status=0 for 3 checks', 60, 3, 'Critical', 'Connectivity', 'Link failure or device powered off', 'Check physical cable and interface status', 'Ping gateway again: ping 192.168.x.1', 1),
('R02', 'High Packet Loss', 'packet_loss_percent > 50', 60, 2, 'Warning', 'Performance', 'Congestion or faulty cable', 'Check interface errors and bandwidth usage', 'Run ping with 10 packets', 1),
('R03', 'High Latency', 'latency_ms > 100', 60, 3, 'Warning', 'Performance', 'Network congestion or long route', 'Check QoS and link utilization', 'Measure latency continuously for 1 min', 1),
('R04', 'HTTP Service Down', 'http_status != 200', 30, 2, 'Critical', 'Service', 'Web server stopped or port blocked', 'Restart HTTP service, check firewall', 'curl http://server-ip', 1),
('R05', 'SNMP Agent Unreachable', 'snmp_cpu_percent IS NULL after request', 60, 2, 'Info', 'Service', 'SNMP disabled or community wrong', 'Enable SNMP and verify community string', 'snmpwalk -v2c -c public device_ip', 1),
('R06', 'Core Switch Unreachable', 'device_type=core_switch AND icmp_status=0', 60, 3, 'Critical', 'Connectivity', 'Core switch failure affects all VLANs', 'Check core switch power and uplinks', 'Ping core switch management IP', 1),
('R07', 'Server Unreachable', 'device_type=server AND icmp_status=0', 60, 3, 'Critical', 'Connectivity', 'Server down or NIC failure', 'Check server power and network config', 'Ping server from multiple VLANs', 1),
('R08', 'Single Host Unreachable', 'device_type=pc AND icmp_status=0 AND vlan_gateway=1', 60, 3, 'Warning', 'Connectivity', 'Host-specific issue, not VLAN-wide', 'Check host firewall and IP config', 'Ping host from same VLAN', 1),
('R09', 'Multiple VLAN Gateways Down', 'COUNT(vlan_gateway_down) >=2 in 60s', 60, 1, 'Critical', 'Correlation', 'Upstream device (Core/Router) failure', 'Check core switch and main router', 'Ping all gateways together', 1),

-- R10 to R15 = New 6 rules - Your suggestion - Realistic and achievable
('R10', 'Device Recovered', 'previous_status=0 AND current_status=1', 60, 1, 'Info', 'Connectivity', 'Device came back online after failure', 'Log recovery and monitor for flapping', 'Check uptime and logs', 1),
('R11', 'Fault Persists Long', 'fault_status=open AND duration > 300s', 300, 1, 'Critical', 'Correlation', 'Fault not resolved for 5+ minutes', 'Escalate to senior admin', 'Verify if device still down', 1),
('R12', 'Intermittent Connectivity', 'status changes UP/DOWN >=3 in 300s', 300, 3, 'Warning', 'Correlation', 'Flapping link or unstable power', 'Check cable, duplex, interface errors', 'Monitor for 10 minutes continuously', 1),
('R13', 'Multiple Devices Fail Together', 'COUNT(devices_down) >=3 in same 60s window', 60, 1, 'Critical', 'Correlation', 'Possible upstream or power failure', 'Check upstream router/switch and power', 'Check common upstream device', 1),
('R14', 'Monitoring Timeout', 'no response within timeout_window', 30, 2, 'Warning', 'Performance', 'Device slow or overloaded', 'Increase timeout, check CPU', 'Ping with longer timeout', 1),
('R15', 'Duplicate Alert Suppression', 'same fault open and new same fault detected', 60, 1, 'Info', 'Correlation', 'Same fault already reported - avoid spam', 'Suppress duplicate, update existing fault', 'Check existing open faults', 1);
