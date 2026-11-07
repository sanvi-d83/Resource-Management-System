import os
import random
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, jsonify, render_template, request, session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash

from alerts import send_low_resource_email

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "resource_management.db")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key-for-local-development")

# Demo login. Change these environment variables before deploying.
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

RESOURCE_CONFIG = {
    "Water": {"unit": "L", "capacity": 10000, "default_threshold": 2500},
    "Electricity": {"unit": "kWh", "capacity": 1000, "default_threshold": 150},
}
BUILDINGS = [
    ("B001", "Computer Science"),
    ("B002", "Library"),
    ("B003", "Administration"),
    ("B004", "Mechanical"),
    ("B005", "Workshop"),
]


@contextmanager
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS buildings (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS resource_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            building_id TEXT NOT NULL,
            resource TEXT NOT NULL,
            value REAL NOT NULL,
            recorded_at TEXT NOT NULL,
            FOREIGN KEY(building_id) REFERENCES buildings(id)
        );
        CREATE TABLE IF NOT EXISTS resource_limits (
            building_id TEXT NOT NULL,
            resource TEXT NOT NULL,
            threshold REAL NOT NULL,
            PRIMARY KEY(building_id, resource),
            FOREIGN KEY(building_id) REFERENCES buildings(id)
        );
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            building_id TEXT NOT NULL,
            resource TEXT NOT NULL,
            current_value REAL NOT NULL,
            threshold REAL NOT NULL,
            message TEXT NOT NULL,
            email_status TEXT NOT NULL DEFAULT 'Not configured',
            created_at TEXT NOT NULL,
            FOREIGN KEY(building_id) REFERENCES buildings(id)
        );
        """)
        for building_id, name in BUILDINGS:
            conn.execute(
                "INSERT OR IGNORE INTO buildings(id, name) VALUES (?, ?)",
                (building_id, name),
            )
            for resource, config in RESOURCE_CONFIG.items():
                conn.execute(
                    """INSERT OR IGNORE INTO resource_limits
                       (building_id, resource, threshold) VALUES (?, ?, ?)""",
                    (building_id, resource, config["default_threshold"]),
                )
                count = conn.execute(
                    "SELECT COUNT(*) FROM resource_readings WHERE building_id=? AND resource=?",
                    (building_id, resource),
                ).fetchone()[0]
                if count == 0:
                    initial = (
                        random.uniform(3500, 9000)
                        if resource == "Water"
                        else random.uniform(250, 900)
                    )
                    conn.execute(
                        """INSERT INTO resource_readings
                           (building_id, resource, value, recorded_at)
                           VALUES (?, ?, ?, ?)""",
                        (building_id, resource, round(initial, 2), datetime.now().isoformat(timespec="seconds")),
                    )


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def latest_reading(conn, building_id, resource):
    return conn.execute(
        """SELECT value, recorded_at FROM resource_readings
           WHERE building_id=? AND resource=?
           ORDER BY id DESC LIMIT 1""",
        (building_id, resource),
    ).fetchone()


def maybe_create_alert(conn, building_id, resource, value, threshold):
    # Create an alert only when the resource is below its limit.
    if value >= threshold:
        return None

    # Avoid creating repeated alerts for every polling cycle.
    previous = conn.execute(
        """SELECT id FROM alerts
           WHERE building_id=? AND resource=?
             AND created_at >= ? ORDER BY id DESC LIMIT 1""",
        (building_id, resource, (datetime.now() - timedelta(minutes=15)).isoformat(timespec="seconds")),
    ).fetchone()
    if previous:
        return None

    building = conn.execute("SELECT name FROM buildings WHERE id=?", (building_id,)).fetchone()
    message = (
        f"{resource} level is below the admin-defined limit in {building['name']} "
        f"({building_id}). Current: {value:g}; minimum: {threshold:g}."
    )
    email_status = send_low_resource_email(
        building_name=building["name"],
        building_id=building_id,
        resource=resource,
        current_value=value,
        threshold=threshold,
        unit=RESOURCE_CONFIG[resource]["unit"],
    )
    conn.execute(
        """INSERT INTO alerts
           (building_id, resource, current_value, threshold, message, email_status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            building_id, resource, value, threshold, message,
            email_status, datetime.now().isoformat(timespec="seconds")
        ),
    )
    return {"message": message, "email_status": email_status}


@app.route("/")
def home():
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == ADMIN_USERNAME and check_password_hash(
            generate_password_hash(ADMIN_PASSWORD), password
        ):
            session["logged_in"] = True
            session["username"] = username
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", username=session.get("username", "admin"))


@app.route("/settings")
@login_required
def settings():
    return render_template("settings.html")


@app.get("/api/overview")
@login_required
def api_overview():
    result = []
    with get_db() as conn:
        buildings = conn.execute("SELECT id, name FROM buildings ORDER BY id").fetchall()
        for building in buildings:
            resources = {}
            for resource, config in RESOURCE_CONFIG.items():
                reading = latest_reading(conn, building["id"], resource)
                limit = conn.execute(
                    "SELECT threshold FROM resource_limits WHERE building_id=? AND resource=?",
                    (building["id"], resource),
                ).fetchone()
                value = reading["value"] if reading else 0
                threshold = limit["threshold"] if limit else config["default_threshold"]
                resources[resource] = {
                    "value": value,
                    "threshold": threshold,
                    "unit": config["unit"],
                    "capacity": config["capacity"],
                    "recorded_at": reading["recorded_at"] if reading else None,
                    "status": "Low" if value < threshold else "Normal",
                }
            result.append({"id": building["id"], "name": building["name"], "resources": resources})
    return jsonify(result)


@app.post("/api/simulate")
@login_required
def api_simulate():
    """Generate one simulated reading per building/resource and save it."""
    new_alerts = []
    with get_db() as conn:
        buildings = conn.execute("SELECT id FROM buildings").fetchall()
        for building in buildings:
            for resource, config in RESOURCE_CONFIG.items():
                previous = latest_reading(conn, building["id"], resource)
                old_value = previous["value"] if previous else config["capacity"] * 0.7

                # Simulate gradual changes with occasional low-level events.
                if resource == "Water":
                    change = random.uniform(-420, 180)
                    value = old_value + change
                    if random.random() < 0.07:
                        value -= random.uniform(1200, 2500)
                    value = max(0, min(config["capacity"], value))
                else:
                    # Electricity is represented as remaining available supply in this demo.
                    change = random.uniform(-45, 28)
                    value = old_value + change
                    if random.random() < 0.07:
                        value -= random.uniform(100, 220)
                    value = max(0, min(config["capacity"], value))

                value = round(value, 2)
                now = datetime.now().isoformat(timespec="seconds")
                conn.execute(
                    """INSERT INTO resource_readings
                       (building_id, resource, value, recorded_at)
                       VALUES (?, ?, ?, ?)""",
                    (building["id"], resource, value, now),
                )
                limit_row = conn.execute(
                    "SELECT threshold FROM resource_limits WHERE building_id=? AND resource=?",
                    (building["id"], resource),
                ).fetchone()
                threshold = limit_row["threshold"] if limit_row else config["default_threshold"]
                alert = maybe_create_alert(conn, building["id"], resource, value, threshold)
                if alert:
                    new_alerts.append(alert)
    return jsonify({"success": True, "new_alerts": new_alerts})


@app.get("/api/history")
@login_required
def api_history():
    building_id = request.args.get("building_id", "B001")
    resource = request.args.get("resource", "Water")
    if resource not in RESOURCE_CONFIG:
        return jsonify({"error": "Unknown resource"}), 400
    with get_db() as conn:
        exists = conn.execute("SELECT id FROM buildings WHERE id=?", (building_id,)).fetchone()
        if not exists:
            return jsonify({"error": "Unknown building"}), 404
        rows = conn.execute(
            """SELECT value, recorded_at FROM resource_readings
               WHERE building_id=? AND resource=?
               ORDER BY id DESC LIMIT 30""",
            (building_id, resource),
        ).fetchall()
    rows = list(reversed(rows))
    return jsonify({
        "labels": [datetime.fromisoformat(row["recorded_at"]).strftime("%H:%M:%S") for row in rows],
        "values": [row["value"] for row in rows],
    })


@app.get("/api/limits")
@login_required
def api_limits():
    with get_db() as conn:
        rows = conn.execute(
            """SELECT l.building_id, b.name AS building_name, l.resource, l.threshold
               FROM resource_limits l JOIN buildings b ON b.id=l.building_id
               ORDER BY l.building_id, l.resource"""
        ).fetchall()
    return jsonify([dict(row) for row in rows])


@app.post("/api/limits")
@login_required
def api_update_limit():
    data = request.get_json(silent=True) or {}
    building_id = data.get("building_id")
    resource = data.get("resource")
    threshold = data.get("threshold")
    if resource not in RESOURCE_CONFIG:
        return jsonify({"error": "Invalid resource"}), 400
    try:
        threshold = float(threshold)
        if threshold < 0 or threshold > RESOURCE_CONFIG[resource]["capacity"]:
            raise ValueError()
    except (TypeError, ValueError):
        return jsonify({"error": f"Threshold must be between 0 and {RESOURCE_CONFIG[resource]['capacity']}."}), 400

    with get_db() as conn:
        building = conn.execute("SELECT id FROM buildings WHERE id=?", (building_id,)).fetchone()
        if not building:
            return jsonify({"error": "Invalid building"}), 404
        conn.execute(
            """INSERT INTO resource_limits(building_id, resource, threshold)
               VALUES (?, ?, ?)
               ON CONFLICT(building_id, resource)
               DO UPDATE SET threshold=excluded.threshold""",
            (building_id, resource, threshold),
        )
    return jsonify({"success": True, "message": "Threshold updated successfully."})


@app.get("/api/alerts")
@login_required
def api_alerts():
    with get_db() as conn:
        rows = conn.execute(
            """SELECT a.*, b.name AS building_name FROM alerts a
               JOIN buildings b ON b.id=a.building_id
               ORDER BY a.id DESC LIMIT 50"""
        ).fetchall()
    return jsonify([dict(row) for row in rows])


@app.get("/api/buildings")
@login_required
def api_buildings():
    with get_db() as conn:
        rows = conn.execute("SELECT id, name FROM buildings ORDER BY id").fetchall()
    return jsonify([dict(row) for row in rows])


init_db()

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
