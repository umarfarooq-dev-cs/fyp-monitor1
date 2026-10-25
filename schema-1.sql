-- ==========================================================
-- FYP: Explainable Rule-Based Network Fault Diagnosis System
-- Database: SQLite
-- Version: FINAL - With Teacher Comments + Your Improvements
-- Author: Umar - Superior Science College Peshawar
-- ==========================================================

-- 1. DEVICES TABLE
-- Why: Stores your EVE-NG topology devices
-- What it holds: Router, Core Switch, VLAN gateways, PCs, Server
-- This is your main table - all other tables link to this
CREATE TABLE devices (
    device_id INTEGER PRIMARY KEY AUTOINCREMENT, -- Auto ID
    device_name VARCHAR(50) NOT NULL UNIQUE, -- e.g., Main-Router
    ip_address VARCHAR(15) NOT NULL, -- e.g., 192.168.10.1
    device_type VARCHAR(20) CHECK(device_type IN ('router','core_switch','access_switch','server','pc','monitor')),
    vlan_id INTEGER, -- 10,20,30,40 for your 4 VLANs
    location VARCHAR(50), -- e.g., Admin Block
    status VARCHAR(10) DEFAULT 'unknown', -- UP/DOWN
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. RULES TABLE
-- Why: Teacher's main requirement - Page 4
-- What it holds: All 15 rules with full explainable format
-- This is your brain - rule engine reads from here
CREATE TABLE rules (
    rule_id TEXT PRIMARY KEY, -- R01 to R15
    rule_name VARCHAR(100) NOT NULL, -- e.g., Gateway Unreachable
    predicate TEXT NOT NULL, -- Condition: "icmp_loss > 75%"
    time_window_seconds INTEGER DEFAULT 60, -- Check for how long
    persistence_count INTEGER DEFAULT 3, -- Must fail 3 times
    severity VARCHAR(10) CHECK(severity IN ('Critical','Warning','Info')),
    category VARCHAR(20) CHECK(category IN ('Connectivity','Service','Performance','Correlation')),
    probable_cause TEXT NOT NULL, -- Why it happened
    recommended_action TEXT NOT NULL, -- What to do
    verification_step TEXT NOT NULL, -- How to verify fix
    enabled INTEGER DEFAULT 1, -- 1=active, 0=disabled
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. METRICS TABLE
-- Why: Stores every ping result - time series data
-- What it holds: Latency, packet loss, status every 60 seconds
-- Simple explanation: This is your diary - every check is written here
CREATE TABLE metrics (
    metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL, -- Which device
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- When checked
    icmp_status INTEGER CHECK(icmp_status IN (0,1)), -- 1=UP, 0=DOWN
    latency_ms REAL, -- e.g., 1.5 ms - Teacher wants units defined
    packet_loss_percent REAL, -- e.g., 0% or 100%
    http_status INTEGER, -- e.g., 200=OK, 0=DOWN
    snmp_cpu_percent REAL, -- NULL if EVE doesn't support - Teacher allows emulated
    interface_status VARCHAR(10), -- UP/DOWN
    FOREIGN KEY(device_id) REFERENCES devices(device_id) ON DELETE CASCADE
);
-- Indexes: Makes Grafana fast - Teacher wants indexes
CREATE INDEX idx_metrics_device_time ON metrics(device_id, timestamp DESC);
CREATE INDEX idx_metrics_time ON metrics(timestamp);
-- Note for proposal: Retention = 30 days raw, hourly after 7 days

-- 4. FAULTS TABLE
-- Why: Stores when fault is detected - fault lifecycle
-- What it holds: Open -> Acknowledged -> Resolved
-- Simple: When rule fires, fault is created here
CREATE TABLE faults (
    fault_id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL, -- Which device failed
    rule_id TEXT, -- Which rule fired - R01 etc
    status VARCHAR(15) CHECK(status IN ('open','acknowledged','resolved','reopened')),
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP, -- When fixed
    evidence TEXT NOT NULL, -- Proof: "Ping failed 3 times"
    FOREIGN KEY(device_id) REFERENCES devices(device_id),
    FOREIGN KEY(rule_id) REFERENCES rules(rule_id)
);
CREATE INDEX idx_faults_device ON faults(device_id);
CREATE INDEX idx_faults_status ON faults(status);
CREATE INDEX idx_faults_time ON faults(detected_at DESC);

-- 5. TEST_SCENARIOS TABLE
-- Why: Teacher Page 5 wants reproducible testing
-- What it holds: What fault you injected, what should happen
CREATE TABLE test_scenarios (
    scenario_id INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_name VARCHAR(100) NOT NULL UNIQUE, -- e.g., "Admin Gateway Down"
    fault_type VARCHAR(50), -- Link down, Shutdown
    injected_device_id INTEGER, -- Which device you shut down
    expected_rule_id TEXT, -- Which rule SHOULD fire
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    FOREIGN KEY(injected_device_id) REFERENCES devices(device_id),
    FOREIGN KEY(expected_rule_id) REFERENCES rules(rule_id)
);

-- 6. TEST_RESULTS TABLE
-- Why: For Precision/Recall calculation - Teacher Page 4 formula
-- What it holds: TP,FP,TN,FN + detection time
CREATE TABLE test_results (
    result_id INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id INTEGER NOT NULL,
    run_number INTEGER NOT NULL, -- Run 1,2,3 for repeatability
    ground_truth VARCHAR(10) CHECK(ground_truth IN ('fault','no_fault')),
    detected_rule_id TEXT,
    outcome VARCHAR(10) CHECK(outcome IN ('TP','FP','TN','FN')), -- True Positive etc
    detection_time_seconds REAL, -- How fast detected
    observed_evidence TEXT,
    tested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(scenario_id) REFERENCES test_scenarios(scenario_id),
    FOREIGN KEY(detected_rule_id) REFERENCES rules(rule_id)
);
CREATE INDEX idx_results_scenario ON test_results(scenario_id);

-- 7. USERS TABLE
-- Why: Security - Teacher Page 5 wants hashed passwords
-- What it holds: Admin and viewer accounts for Flask
CREATE TABLE users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(30) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL, -- NEVER plain password - use werkzeug
    role VARCHAR(15) CHECK(role IN ('admin','viewer')) DEFAULT 'viewer',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 8. RULE_EXECUTION_LOG TABLE - YOUR IMPROVEMENT #1
-- Why: You suggested - Teacher may ask "When was each rule executed?"
-- What it holds: Every time rule engine runs, log it here
-- Simple: Debugging becomes easy - you know what happened when
CREATE TABLE rule_execution_log (
    execution_id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id TEXT NOT NULL, -- Which rule ran
    device_id INTEGER NOT NULL, -- On which device
    result VARCHAR(10) CHECK(result IN ('fired','not_fired','error')), -- What happened
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    details TEXT, -- Extra info: "Latency was 150ms"
    FOREIGN KEY(rule_id) REFERENCES rules(rule_id),
    FOREIGN KEY(device_id) REFERENCES devices(device_id)
);
CREATE INDEX idx_exec_log_rule ON rule_execution_log(rule_id);
CREATE INDEX idx_exec_log_time ON rule_execution_log(executed_at DESC);

-- 9. ALERTS TABLE - YOUR IMPROVEMENT #2
-- Why: You suggested - Separate from faults, for Flask display
-- What it holds: Alerts for dashboard - like notification inbox
-- Simple: Faults = technical, Alerts = user notification
CREATE TABLE alerts (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,
    severity VARCHAR(10) CHECK(severity IN ('Critical','Warning','Info')),
    message TEXT NOT NULL, -- e.g., "Admin Gateway is DOWN"
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    read_status INTEGER DEFAULT 0 CHECK(read_status IN (0,1)), -- 0=unread, 1=read
    FOREIGN KEY(device_id) REFERENCES devices(device_id)
);
CREATE INDEX idx_alerts_read ON alerts(read_status);
CREATE INDEX idx_alerts_time ON alerts(created_at DESC);

-- TOTAL: 9 Tables - 7 Core + 2 Improvements = 99/100 as you said
