
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
app.config['DATABASE'] = os.getenv('DB_PATH', 'database.db')
app.config['DEBUG'] = os.getenv('FLASK_ENV') != 'production'
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@contextmanager
def get_db():
    conn = None
    try:
        conn = sqlite3.connect(app.config['DATABASE'])
        conn.row_factory = sqlite3.Row
        yield conn
    except sqlite3.Error as e:
        logger.error(f"DB Error: {e}")
        raise
    finally:
        if conn:
            conn.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health():
    return jsonify({"status": "ok", "db_exists": os.path.exists(app.config['DATABASE']), "time": datetime.now().isoformat()})

@app.route('/api/overview')
def api_overview():
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) as total FROM devices")
            total = cur.fetchone()['total']
            cur.execute("SELECT COUNT(*) as online FROM devices WHERE UPPER(status) IN ('UP','ONLINE','ON','1')")
            online = cur.fetchone()['online']
            offline = total - online
            return jsonify({"total": total, "online": online, "offline": offline, "critical": offline, "warning": 0})
    except Exception as e:
        return jsonify({"total": 0, "online": 0, "offline": 0, "critical": 0, "warning": 0})

# --- FIXED FOR YOUR REAL TABLE: device_id / device_name ---
@app.route('/api/devices')
def api_devices():
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM devices ORDER BY device_id")
            out = []
            for r in cur.fetchall():
                d = dict(r)
                # Map REAL columns -> what frontend expects
                d['id'] = d.get('device_id')
                d['device_id'] = d.get('device_id')
                d['name'] = d.get('device_name') or 'Device'
                d['hostname'] = d.get('device_name') or 'Device'
                d['device_name'] = d.get('device_name')
                d['ip'] = d.get('ip_address') or ''
                d['ip_address'] = d.get('ip_address') or ''
                s = str(d.get('status') or '').upper()
                if s in ('UP','ONLINE','ON','1','TRUE'):
                    d['status'] = 'UP'
                elif s in ('DOWN','OFFLINE','OFF','0','FALSE','FAULT'):
                    d['status'] = 'DOWN'
                out.append(d)
            return jsonify(out)
    except Exception as e:
        logger.error(f"/api/devices failed: {e}")
        return jsonify({"error": "Failed to fetch devices", "detail": str(e)}), 500

@app.route('/api/faults')
def api_faults():
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT f.id, f.device_id, d.device_name as device, f.rule_id,
                       r.severity, r.description, f.detected_at, f.status
                FROM fault_history f
                JOIN devices d ON f.device_id = d.device_id
                LEFT JOIN rules r ON f.rule_id = r.rule_id
                WHERE f.status IN ('open','active')
                ORDER BY f.detected_at DESC
            """)
            return jsonify([dict(r) for r in cur.fetchall()])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/recommendation/<rule_id>')
def api_recommendation(rule_id):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT rule_id, probable_cause, recommended_action, verification_step, severity FROM rules WHERE rule_id = ?", (rule_id,))
            row = cur.fetchone()
            if row:
                return jsonify(dict(row))
            return jsonify({"error": "Rule not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/history')
def api_history():
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

@app.route('/api/fault/<int:fault_id>/acknowledge', methods=['POST'])
def api_acknowledge(fault_id):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE fault_history SET status='acknowledged', acknowledged_at=? WHERE id=?", (datetime.now().isoformat(), fault_id))
            if cur.rowcount == 0:
                return jsonify({"error": "Fault ID not found"}), 404
            conn.commit()
            return jsonify({"status": "acknowledged", "id": fault_id})
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

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint not found"}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=app.config['DEBUG'])
