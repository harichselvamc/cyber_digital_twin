import time
import threading
import secrets
from typing import List, Dict, Optional

from flask import Flask, render_template, request, redirect, session, jsonify, send_file

from behavior_collector import BehaviorCollector
from model import DigitalTwinModel
import storage
import risk_logger
import soc_monitor

from windows_lock import lock_windows
from analytics import evaluate_far_frr
from explainability import explain
from replay_engine import build_replay_sequence
from attacker_simulator import generate_attacker_features
from confidence import confidence_score
from fingerprint import fingerprint_similarity
from report_generator import generate_report


app = Flask(__name__)
app.secret_key = "dev-secret-change-me"

USERS = {"admin": "admin123", "user2": "pass123"}

collector = BehaviorCollector(window_seconds=10.0)
dtm = DigitalTwinModel()

_monitor_thread: Optional[threading.Thread] = None
_monitor_running = False

_attack_mode = False
_attack_level = 3
_attack_start_ts: Optional[float] = None

_current_user = "unknown"

_latest_risk = {
    "risk_score": 0,
    "level": "LOW",
    "action": "ALLOW",
    "confidence": 100,
    "fingerprint_score": 100,
    "ts": 0,
    "otp_required": False,
    "features": {},
    "attack_mode": False,
    "attack_level": 0,
}

# =====================================================
#  SECURITY RESET (NEW)
# =====================================================
def reset_security_state():
    global _attack_mode, _attack_level, _attack_start_ts, _latest_risk

    _attack_mode = False
    _attack_level = 0
    _attack_start_ts = None

    _latest_risk = {
        "risk_score": 0,
        "level": "LOW",
        "action": "ALLOW",
        "confidence": 100,
        "fingerprint_score": 100,
        "ts": 0,
        "otp_required": False,
        "features": {},
        "attack_mode": False,
        "attack_level": 0,
    }

    print(" SECURITY STATE RESET")


# =====================================================
# ROUTES
# =====================================================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    global _current_user

    if request.method == "POST":
        u = request.form.get("username")
        p = request.form.get("password")

        if USERS.get(u) == p:
            reset_security_state()   

            session.clear()
            session["user"] = u
            session["otp_verified"] = True
            _current_user = u

            model = storage.load_model(u)
            if model:
                dtm.model = model
                print("Loaded Digital Twin:", u)

            return redirect("/dashboard")

        return render_template("login.html", error="Invalid credentials")

    return render_template("login.html", error=None)


@app.route("/logout")
def logout():
    global _current_user
    stop_monitoring()
    reset_security_state()  
    session.clear()
    _current_user = "unknown"
    return redirect("/")


@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login")
    return render_template("dashboard.html", user=session["user"])


@app.route("/soc")
def soc():
    return render_template("soc.html")


# =====================================================
# ENROLLMENT
# =====================================================
@app.route("/enroll", methods=["GET", "POST"])
def enroll():
    global _current_user

    if "user" not in session:
        return redirect("/login")

    if request.method == "POST":
        user = session["user"]
        _current_user = user

        seconds = float(request.form.get("seconds", "60"))
        interval = float(request.form.get("interval", "2"))

        samples: List[Dict[str, float]] = []

        collector.start()
        end = time.time() + seconds

        while time.time() < end:
            snap = collector.snapshot()
            samples.append(snap.features)
            time.sleep(interval)

        dtm.train(samples)
        storage.save_samples(user, samples)
        storage.save_model(user, dtm.model)

        return render_template("enroll.html", done=True, count=len(samples))

    return render_template("enroll.html", done=False, count=0)


# =====================================================
# OTP
# =====================================================
def generate_otp():
    return str(secrets.randbelow(900000) + 100000)


@app.route("/otp", methods=["GET", "POST"])
def otp():
    if "user" not in session:
        return redirect("/login")

    error = None

    if "otp_code" not in session:
        session["otp_code"] = generate_otp()
        session["otp_exp"] = time.time() + 120
        session["otp_verified"] = False

    if request.method == "POST":
        code = request.form.get("otp")

        if time.time() > session["otp_exp"]:
            error = "OTP expired"
            session.pop("otp_code", None)

        elif code == session["otp_code"]:
            session["otp_verified"] = True
            session.pop("otp_code", None)
            return redirect("/dashboard")
        else:
            error = "Invalid OTP"

    return render_template("otp.html", error=error, otp_demo=session.get("otp_code"))


# =====================================================
# MONITOR CONTROL
# =====================================================
@app.route("/api/start_monitor", methods=["POST"])
def api_start_monitor():
    reset_security_state()  
    start_monitoring()
    return jsonify({"ok": True})


@app.route("/api/stop_monitor", methods=["POST"])
def api_stop_monitor():
    stop_monitoring()
    return jsonify({"ok": True})


# =====================================================
# ATTACK MODE
# =====================================================
@app.route("/api/attack_mode", methods=["POST"])
def api_attack_mode():
    global _attack_mode, _attack_level, _attack_start_ts

    data = request.get_json(silent=True) or {}
    _attack_mode = bool(data.get("enable", False))
    _attack_level = int(data.get("level", 3))

    if _attack_mode:
        _attack_start_ts = time.time()
    else:
        _attack_start_ts = None

    print("ATTACK:", _attack_mode, "LEVEL:", _attack_level)
    return jsonify({"attack_mode": _attack_mode, "level": _attack_level})


# =====================================================
#  RESET ENDPOINT
# =====================================================
@app.route("/api/reset_security", methods=["POST"])
def api_reset_security():
    stop_monitoring()
    reset_security_state()
    return jsonify({"reset": True})


# =====================================================
# RISK API
# =====================================================
@app.route("/api/risk")
def api_risk():
    if _latest_risk["action"] == "BLOCK":
        stop_monitoring()
        reset_security_state()  

    return jsonify(_latest_risk)


# =====================================================
# ANALYTICS
# =====================================================
@app.route("/api/analytics")
def api_analytics():
    return jsonify(evaluate_far_frr(session.get("user")))


@app.route("/api/explain")
def api_explain():
    return jsonify(explain(_latest_risk["features"]))


@app.route("/api/replay")
def api_replay():
    return jsonify(build_replay_sequence())


@app.route("/api/confidence")
def api_confidence():
    return jsonify({"confidence": _latest_risk["confidence"]})


@app.route("/api/fingerprint")
def api_fingerprint():
    return jsonify({"fingerprint": _latest_risk["fingerprint_score"]})


@app.route("/api/soc_live")
def api_soc_live():
    return jsonify(soc_monitor.get_live_users())


@app.route("/api/export_report")
def api_export_report():
    path = generate_report()
    return send_file(path, as_attachment=True)


@app.route("/api/heatmap")
def api_heatmap():
    history = risk_logger.load_history()
    buckets = [0] * 24
    for h in history:
        hour = int((h["ts"] % 86400) // 3600)
        buckets[hour] += 1
    return jsonify(buckets)


# =====================================================
# MONITOR LOOP
# =====================================================
def monitor_loop():
    global _latest_risk, _monitor_running

    collector.start()
    last_lock = 0.0

    while _monitor_running:

        if _attack_mode:
            features = generate_attacker_features(
                level=_attack_level,
                start_ts=_attack_start_ts
            )
        else:
            features = collector.snapshot().features

        res = dtm.evaluate(features)

        _latest_risk = {
            "risk_score": res.risk_score,
            "level": res.level,
            "action": res.action,
            "confidence": confidence_score(res.anomaly_score),
            "fingerprint_score": fingerprint_similarity(features),
            "ts": time.time(),
            "otp_required": (res.action == "STEP_UP"),
            "features": features,
            "attack_mode": _attack_mode,
            "attack_level": _attack_level,
        }

        risk_logger.log_risk(_latest_risk)
        soc_monitor.update_user(_current_user, _latest_risk)

        if res.action == "BLOCK":
            now = time.time()
            if now - last_lock > 30:
                lock_windows()
                last_lock = now

        time.sleep(1)


def start_monitoring():
    global _monitor_running, _monitor_thread
    if _monitor_running:
        return

    _monitor_running = True
    _monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
    _monitor_thread.start()


def stop_monitoring():
    global _monitor_running
    _monitor_running = False


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)