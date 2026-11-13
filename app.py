# app.py - Flask Dashboard Backend
# Matched with: schema-1.sql + seed-rules.sql + insert.py + monitor_db.py
# DB: network_monitor.db
import os
import sqlite3
import logging
from datetime import datetime
from contextlib import contextmanager
from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-fallback-key-change-in-prod')
# FIX 1: DB name must match insert.py and monitor_db.py
app.config['DATABASE'] = os.getenv('DB_PATH', 'network_monitor.db')
app.config['DEBUG'] = os.getenv('FLASK_ENV') != 'production'
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@contextmanager
def get_db():
    conn = None
    try:
        conn = sqlite3.connect(app.config['DATABASE'])
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"DB Error: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health():
    return jsonify({
        "status": "ok",
        "db_exists": os.path.exists(app.config['DATABASE']),
        "db": app.config['DATABASE'],
        "time": datetime.now().isoformat()
    })

@app.route('/api/overview')
def api_overview():
    """Dashboard overview - Total / Online / Offline / Critical / Warning from real faults."""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) as total FROM devices")
            total = cur.fetchone()['total']

            cur.execute("SELECT COUNT(*) as online FROM devices WHERE UPPER(status) = 'UP'")
            online = cur.fetchone()['online']
            offline = total - online

            # FIX 4: Critical / Warning from open faults, not hard-coded
            cur.execute("""
                SELECT COUNT(*) as critical FROM faults f
                JOIN rules r ON f.rule_id = r.rule_id
                WHERE f.status = 'open' AND r.severity = 'Critical'
            """)
            critical = cur.fetchone()['critical']

            cur.execute("""
                SELECT COUNT(*) as warning FROM faults f
                JOIN rules r ON f.rule_id = r.rule_id
                WHERE f.status = 'open' AND r.severity = 'Warning'
            """)
            warning = cur.fetchone()['warning']

            cur.execute("SELECT COUNT(*) as open_faults FROM faults WHERE status = 'open'")
            open_faults = cur.fetchone()['open_faults']

            return jsonify({
                "total": total,
                "online": online,
                "offline": offline,
                "critical": critical,
                "warning": warning,
                "open_faults": open_faults
            })
    except Exception as e:
        logger.error(f"/api/overview failed: {e}")
        return jsonify({"total": 0, "online": 0, "offline": 0, "critical": 0, "warning": 0, "open_faults": 0})

@app.route('/api/devices')
def api_devices():
    """All devices with status normalized to UP/DOWN."""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM devices ORDER BY device_id")
            out = []
            for r in cur.fetchall():
                d = dict(r)
                d['id'] = d.get('device_id')
                d['name'] = d.get('device_name') or 'Device'
                d['hostname'] = d.get('device_name') or 'Device'
                d['ip'] = d.get('ip_address') or ''
                s = str(d.get('status') or '').upper()
                if s in ('UP', 'ONLINE', 'ON', '1', 'TRUE'):
                    d['status'] = 'UP'
                elif s in ('DOWN', 'OFFLINE', 'OFF', '0', 'FALSE', 'FAULT', 'UNKNOWN'):
                    # UNKNOWN means not yet monitored - show as DOWN only if explicitly DOWN
                    d['status'] = 'DOWN' if s == 'DOWN' else s
                # Keep original for frontend: if status is unknown, show as UNKNOWN
                if s == 'UNKNOWN':
                    d['status'] = 'UNKNOWN'
                out.append(d)
            return jsonify(out)
    except Exception as e:
        logger.error(f"/api/devices failed: {e}")
        return jsonify({"error": "Failed to fetch devices", "detail": str(e)}), 500

@app.route('/api/faults')
def api_faults():
    """
    FIX 2: Correct columns for real schema.
    faults: fault_id, device_id, rule_id, status, detected_at, resolved_at, evidence
    rules: rule_name, severity, probable_cause, recommended_action, verification_step
    devices: device_name, ip_address
    """
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT
                    f.fault_id as id,
                    f.fault_id,
                    f.device_id,
                    d.device_name as device,
                    d.device_name as device_name,
                    d.ip_address as ip,
                    f.rule_id,
                    r.rule_name,
                    r.severity,
                    r.probable_cause as description,
                    r.probable_cause,
                    r.recommended_action,
                    r.verification_step,
                    f.detected_at,
                    f.resolved_at,
                    f.status,
                    f.evidence
                FROM faults f
                JOIN devices d ON f.device_id = d.device_id
                LEFT JOIN rules r ON f.rule_id = r.rule_id
                WHERE f.status IN ('open', 'acknowledged')
                ORDER BY f.detected_at DESC
            """)
            return jsonify([dict(r) for r in cur.fetchall()])
    except Exception as e:
        logger.error(f"/api/faults failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/alerts')
def api_alerts():
    """Dashboard alerts from fault_history - Correct columns: alert_id, created_at, read_status, message."""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            limit = min(max(request.args.get('limit', 50, type=int), 1), 200)
            cur.execute("""
                SELECT
                    fh.alert_id as id,
                    fh.alert_id,
                    fh.device_id,
                    d.device_name as device,
                    fh.severity,
                    fh.message,
                    fh.created_at,
                    fh.read_status
                FROM fault_history fh
                JOIN devices d ON fh.device_id = d.device_id
                ORDER BY fh.created_at DESC LIMIT ?
            """, (limit,))
            return jsonify([dict(r) for r in cur.fetchall()])
    except Exception as e:
        logger.error(f"/api/alerts failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/recommendation/<rule_id>')
def api_recommendation(rule_id):
    """Explainable recommendation for a rule - Cause + Action + Verification."""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT rule_id, rule_name, probable_cause, recommended_action, verification_step, severity, category
                FROM rules WHERE rule_id = ?
            """, (rule_id,))
            row = cur.fetchone()
            if row:
                return jsonify(dict(row))
            return jsonify({"error": "Rule not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/history')
def api_history():
    """Recent metrics - Detailed fault metrics only."""
    limit = min(max(request.args.get('limit', 100, type=int), 1), 500)
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT m.*, d.device_name as device_name
                FROM metrics m
                JOIN devices d ON m.device_id = d.device_id
                ORDER BY m.timestamp DESC LIMIT ?
            """, (limit,))
            return jsonify([dict(r) for r in cur.fetchall()])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/hourly')
def api_hourly():
    """Hourly summary for charts - From metrics_hourly (Tiered Storage)."""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            device_id = request.args.get('device_id', type=int)
            if device_id:
                cur.execute("""
                    SELECT mh.*, d.device_name
                    FROM metrics_hourly mh
                    JOIN devices d ON mh.device_id = d.device_id
                    WHERE mh.device_id = ?
                    ORDER BY mh.hour_start DESC LIMIT 24
                """, (device_id,))
            else:
                cur.execute("""
                    SELECT mh.*, d.device_name
                    FROM metrics_hourly mh
                    JOIN devices d ON mh.device_id = d.device_id
                    ORDER BY mh.hour_start DESC LIMIT 100
                """)
            return jsonify([dict(r) for r in cur.fetchall()])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/rules')
def api_rules():
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM rules ORDER BY rule_id")
            return jsonify([dict(r) for r in cur.fetchall()])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/fault/<int:fault_id>/acknowledge', methods=['POST'])
def api_acknowledge(fault_id):
    """
    FIX 3: Acknowledge in faults table, not fault_history.
    faults table has: status, fault_id - No acknowledged_at column.
    """
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE faults SET status = 'acknowledged' WHERE fault_id = ? AND status = 'open'",
                (fault_id,)
            )
            if cur.rowcount == 0:
                return jsonify({"error": "Fault ID not found or already acknowledged"}), 404
            return jsonify({"status": "acknowledged", "id": fault_id})
    except Exception as e:
        logger.error(f"/api/fault acknowledge failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/fault/<int:fault_id>/resolve', methods=['POST'])
def api_resolve(fault_id):
    """Mark fault as resolved."""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE faults SET status = 'resolved', resolved_at = ? WHERE fault_id = ?",
                (datetime.now().isoformat(), fault_id)
            )
            if cur.rowcount == 0:
                return jsonify({"error": "Fault ID not found"}), 404
            return jsonify({"status": "resolved", "id": fault_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/stats')
def api_stats():
    """Evaluation stats - Precision / Recall from test_results + Rule Accuracy from rule_firings."""
    try:
        with get_db() as conn:
            cur = conn.cursor()

            # Test results counts
            cur.execute("SELECT outcome, COUNT(*) as c FROM test_results GROUP BY outcome")
            outcomes = {r['outcome']: r['c'] for r in cur.fetchall()}
            tp = outcomes.get('TP', 0)
            fp = outcomes.get('FP', 0)
            tn = outcomes.get('TN', 0)
            fn = outcomes.get('FN', 0)

            precision = round(tp / (tp + fp) * 100, 2) if (tp + fp) > 0 else 0
            recall = round(tp / (tp + fn) * 100, 2) if (tp + fn) > 0 else 0
            f1 = round(2 * precision * recall / (precision + recall), 2) if (precision + recall) > 0 else 0

            # Rule firing accuracy
            cur.execute("SELECT result, COUNT(*) as c FROM rule_firings GROUP BY result")
            firings = {r['result']: r['c'] for r in cur.fetchall()}

            return jsonify({
                "TP": tp, "FP": fp, "TN": tn, "FN": fn,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "rule_firings": firings
            })
    except Exception as e:
        logger.error(f"/api/stats failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint not found"}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=app.config['DEBUG'])
