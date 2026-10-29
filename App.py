import os
import sqlite3
import logging
from datetime import datetime
from contextlib import contextmanager
from flask import Flask, jsonify, render_template, request, g
from dotenv import load_dotenv

# Load .env
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-fallback-key-change-in-prod')
app.config['DATABASE'] = os.getenv('DB_PATH', 'database.db')
app.config['DEBUG'] = os.getenv('FLASK_ENV') != 'production'

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@contextmanager
def get_db():
    """Secure DB connection with auto-close - no leaks"""
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

# --- Module 1: Dashboard ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health():
    """For teacher to check if backend is alive"""
    return jsonify({"status": "ok", "db_exists": os.path.exists(app.config['DATABASE']), "time": datetime.now().isoformat()})

# --- Module 2: Device Status ---
@app.route('/api/devices')
def api_devices():
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, hostname, device_type, ip_address, vlan_id, status, location, last_seen
                FROM devices ORDER BY id
            """)
            return jsonify([dict(r) for r in cur.fetchall()])
    except Exception as e:
        logger.error(f"/api/devices failed: {e}")
        return jsonify({"error": "Failed to fetch devices"}), 500

# --- Module 3: Active Faults ---
@app.route('/api/faults')
def api_faults():
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT f.id, f.device_id, d.hostname as device, f.rule_id, 
                       r.severity, r.description, f.detected_at, f.status
                FROM fault_history f
                JOIN devices d ON f.device_id = d.id
                LEFT JOIN rules r ON f.rule_id = r.rule_id
                WHERE f.status IN ('open','active')
                ORDER BY f.detected_at DESC
            """)
            return jsonify([dict(r) for r in cur.fetchall()])
    except sqlite3.OperationalError as e:
        return jsonify({"error": f"Table missing: {e}", "hint": "Run schema-1.sql"}), 500

# --- Module 4: Recommendations (USP) ---
@app.route('/api/recommendation/<rule_id>')
def api_recommendation(rule_id):
    if not rule_id or len(rule_id) > 20: # Basic validation
        return jsonify({"error": "Invalid rule_id"}), 400
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT rule_id, probable_cause, recommended_action, verification_step, severity
                FROM rules WHERE rule_id = ?
            """, (rule_id,))
            row = cur.fetchone()
            if row:
                return jsonify(dict(row))
            return jsonify({"error": "Rule not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Module 5: History ---
@app.route('/api/history')
def api_history():
    limit = request.args.get('limit', 100, type=int)
    limit = min(max(limit, 1), 500) # Prevent abuse
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT m.*, d.hostname as device_name 
                FROM metrics m
                JOIN devices d ON m.device_id = d.id
                ORDER BY m.timestamp DESC LIMIT ?
            """, (limit,))
            return jsonify([dict(r) for r in cur.fetchall()])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Module 6: Acknowledge ---
@app.route('/api/fault/<int:fault_id>/acknowledge', methods=['POST'])
def api_acknowledge(fault_id):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE fault_history SET status='acknowledged', acknowledged_at=?
                WHERE id=?
            """, (datetime.now().isoformat(), fault_id))
            if cur.rowcount == 0:
                return jsonify({"error": "Fault ID not found"}), 404
            conn.commit()
            logger.info(f"Fault {fault_id} acknowledged")
            return jsonify({"status": "acknowledged", "id": fault_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Extra ---
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
    if not os.path.exists(app.config['DATABASE']):
        logger.warning(f"DB {app.config['DATABASE']} not found! Create it first.")
    app.run(host='0.0.0.0', port=5000, debug=app.config['DEBUG'])
