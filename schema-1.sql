-- ==========================================================
-- FYP: Explainable Rule-Based Network Fault Diagnosis System
-- Database: SQLite
-- Version: FINAL - With Teacher Comments + Tiered Storage
-- ==========================================================

-- 1. DEVICES
CREATE TABLE devices (
    device_id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_name VARCHAR(50) NOT NULL UNIQUE,
    ip_address VARCHAR(15) NOT NULL,
    device_type VARCHAR(20) CHECK(device_type IN ('router','core_switch','access_switch','server','pc','monitor')),
    vlan_id INTEGER,
    location VARCHAR(50),
    status VARCHAR(10) DEFAULT 'unknown',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. RULES - 25 Rules
CREATE TABLE rules (
    rule_id TEXT PRIMARY KEY,
    rule_name VARCHAR(100) NOT NULL,
    predicate TEXT NOT NULL,
    time_window_seconds INTEGER DEFAULT 60,
    persistence_count INTEGER DEFAULT 3,
    severity VARCHAR(10) CHECK(severity IN ('Critical','Warning','Info')),
    category VARCHAR(20) CHECK(category IN ('Connectivity','Service','Performance','Correlation')),
    probable_cause TEXT NOT NULL,
    recommended_action TEXT NOT NULL,
    verification_step TEXT NOT NULL,
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. METRICS - Detailed per-poll data (only for faults)
CREATE TABLE metrics (
    metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    icmp_status INTEGER CHECK(icmp_status IN (0,1)),
    latency_ms REAL,
    packet_loss_percent REAL,
    http_status INTEGER,
    snmp_cpu_percent REAL,
    interface_status VARCHAR(10),
    port_status VARCHAR(10),
    dns_status INTEGER,
    ip_address_assigned VARCHAR(15),
    mac_address VARCHAR(17),
    FOREIGN KEY(device_id) REFERENCES devices(device_id) ON DELETE CASCADE
);
CREATE INDEX idx_metrics_device_time ON metrics(device_id, timestamp DESC);
CREATE INDEX idx_metrics_time ON metrics(timestamp);

-- 3B. METRICS_HOURLY - Tiered Storage: Normal data as hourly summary only
-- Reduces storage by ~97%, detailed data kept only for faults
CREATE TABLE metrics_hourly (
    hourly_id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,
    hour_start TIMESTAMP NOT NULL,
    avg_latency_ms REAL,
    max_packet_loss REAL,
    up_count INTEGER,
    down_count INTEGER,
    UNIQUE(device_id, hour_start),
    FOREIGN KEY(device_id) REFERENCES devices(device_id) ON DELETE CASCADE
);
CREATE INDEX idx_hourly_device ON metrics_hourly(device_id, hour_start DESC);

-- 4. FAULTS
CREATE TABLE faults (
    fault_id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,
    rule_id TEXT,
    status VARCHAR(15) CHECK(status IN ('open','acknowledged','resolved','reopened')),
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    evidence TEXT,
    FOREIGN KEY(device_id) REFERENCES devices(device_id),
    FOREIGN KEY(rule_id) REFERENCES rules(rule_id)
);
CREATE INDEX idx_faults_device ON faults(device_id);
CREATE INDEX idx_faults_status ON faults(status);
CREATE INDEX idx_faults_time ON faults(detected_at DESC);

-- 5. TEST_SCENARIOS
CREATE TABLE test_scenarios (
    scenario_id INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_name VARCHAR(100) NOT NULL UNIQUE,
    fault_type VARCHAR(50),
    injected_device_id INTEGER,
    expected_rule_id TEXT,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    FOREIGN KEY(injected_device_id) REFERENCES devices(device_id),
    FOREIGN KEY(expected_rule_id) REFERENCES rules(rule_id)
);

-- 6. TEST_RESULTS - For Precision / Recall
CREATE TABLE test_results (
    result_id INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id INTEGER NOT NULL,
    run_number INTEGER NOT NULL,
    ground_truth VARCHAR(10) CHECK(ground_truth IN ('fault','no_fault')),
    detected_rule_id TEXT,
    outcome VARCHAR(10) CHECK(outcome IN ('TP','FP','TN','FN')),
    detection_time_seconds REAL,
    observed_evidence TEXT,
    tested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(scenario_id) REFERENCES test_scenarios(scenario_id),
    FOREIGN KEY(detected_rule_id) REFERENCES rules(rule_id)
);
CREATE INDEX idx_results_scenario ON test_results(scenario_id);

-- 7. USERS
CREATE TABLE users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(30) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(15) CHECK(role IN ('admin','viewer')) DEFAULT 'viewer',
    login_fail_count INTEGER DEFAULT 0,
    last_fail_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 8. RULE_FIRINGS - Rule execution log
CREATE TABLE rule_firings (
    execution_id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id TEXT NOT NULL,
    device_id INTEGER NOT NULL,
    result VARCHAR(10) CHECK(result IN ('fired','not_fired','error')),
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    details TEXT,
    FOREIGN KEY(rule_id) REFERENCES rules(rule_id),
    FOREIGN KEY(device_id) REFERENCES devices(device_id)
);
CREATE INDEX idx_exec_log_rule ON rule_firings(rule_id);
CREATE INDEX idx_exec_log_time ON rule_firings(executed_at DESC);

-- 9. FAULT_HISTORY - Alerts for dashboard
CREATE TABLE fault_history (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,
    severity VARCHAR(10) CHECK(severity IN ('Critical','Warning','Info')),
    message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    read_status INTEGER DEFAULT 0 CHECK(read_status IN (0,1)),
    FOREIGN KEY(device_id) REFERENCES devices(device_id)
);
CREATE INDEX idx_alerts_read ON fault_history(read_status);
CREATE INDEX idx_alerts_time ON fault_history(created_at DESC);
