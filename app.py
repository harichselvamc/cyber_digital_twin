import time
import secrets
import threading
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor

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

# =====================================================
# CORE OBJECTS
# =====================================================

collector = BehaviorCollector(window_seconds=10.0)
dtm = DigitalTwinModel()

_monitor_executor = ThreadPoolExecutor(max_workers=1)
_monitor_stop_event = threading.Event()
_monitor_lock = threading.Lock()
_monitor_future = None

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
# RESET
# =====================================================

def reset_security_state():
    global _attack_mode, _attack_level, _attack_start_ts, _latest_risk

    with _monitor_lock:
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

# =====================================================
# MONITOR LOOP (REALISTIC + PERSISTENT)
# =====================================================

def monitor_loop(user):
    global _latest_risk

    model = storage.load_model(user)
    if model:
        dtm.model = model

    collector.start()

    # Lock control
    last_lock = 0.0
    LOCK_COOLDOWN_SECONDS = 10.0  # prevent repeated locking spam

    # Persistence control: require consecutive "BLOCK" decisions before locking
    block_streak = 0
    REQUIRED_BLOCK_STREAK = 2  # realistic persistence (not time-based)

    while not _monitor_stop_event.is_set():

        start_cycle = time.time()

        try:
            # -------------------------
            # FEATURE SOURCE
            # -------------------------
            if _attack_mode:
                features = generate_attacker_features(
                    level=_attack_level,
                    start_ts=_attack_start_ts
                )
            else:
                features = collector.snapshot().features

            # -------------------------
            # OPTIONAL POLICY BOOST
            # -------------------------
            policy_boost = 0.0
            if _attack_mode and _attack_level >= 3:
                policy_boost = 10.0

            # Model evaluation
            res = dtm.evaluate(features, policy_boost=policy_boost)

            # -------------------------
            # Fingerprint -> risk adjustment
            # -------------------------
            fp = fingerprint_similarity(features)

            adjusted_risk = float(res.risk_score)
            if fp < 60:
                adjusted_risk = min(100.0, adjusted_risk + 10.0)
            if fp < 40:
                adjusted_risk = min(100.0, adjusted_risk + 20.0)

            # Update action based on adjusted_risk thresholds
            action = res.action
            level = res.level
            if adjusted_risk >= dtm.high_threshold:
                action = "BLOCK"
                level = "HIGH"
            elif adjusted_risk >= dtm.low_threshold and action != "BLOCK":
                action = "STEP_UP"
                level = "MEDIUM"

            # -------------------------
            # Build risk_data
            # -------------------------
            risk_data = {
                "risk_score": adjusted_risk,
                "level": level,
                "action": action,
                "confidence": confidence_score(res.anomaly_score),
                "fingerprint_score": fp,
                "ts": time.time(),
                "otp_required": (action == "STEP_UP"),
                "features": features,
                "attack_mode": _attack_mode,
                "attack_level": _attack_level,
            }

            with _monitor_lock:
                _latest_risk = risk_data

            risk_logger.log_risk(risk_data)
            soc_monitor.update_user(user, risk_data)

            # -------------------------
            # REALISTIC ENFORCEMENT: persistence-based lock
            # -------------------------
            if action == "BLOCK":
                block_streak += 1
            else:
                block_streak = 0

            if block_streak >= REQUIRED_BLOCK_STREAK:
                now = time.time()
                if now - last_lock >= LOCK_COOLDOWN_SECONDS:
                    print("🚨 BLOCK confirmed (persistent). Locking Windows.")
                    lock_windows()
                    last_lock = now

        except Exception as e:
            print("Monitor error:", e)

        # Adaptive sleep
        elapsed = time.time() - start_cycle
        sleep_time = max(0.3, 1.0 - elapsed)
        time.sleep(sleep_time)

# =====================================================
# MONITOR CONTROL
# =====================================================

def start_monitoring():
    global _monitor_future

    if "user" not in session:
        return

    if _monitor_future and not _monitor_future.done():
        return

    _monitor_stop_event.clear()
    user = session["user"]

    _monitor_future = _monitor_executor.submit(monitor_loop, user)


def stop_monitoring():
    _monitor_stop_event.set()

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
            return redirect("/dashboard")

        return render_template("login.html", error="Invalid credentials")

    return render_template("login.html", error=None)


@app.route("/logout")
def logout():
    stop_monitoring()
    reset_security_state()
    session.clear()
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

        seconds = float(request.form.get("seconds", "90"))
        interval = float(request.form.get("interval", "2"))

        samples: List[Dict[str, float]] = []

        collector.start()
        end = time.time() + seconds

        while time.time() < end:
            snap = collector.snapshot()
            samples.append(snap.features)
            time.sleep(interval)

        # ✅ IMPORTANT FIX: delete old model before training new one
        storage.delete_model(user)
        dtm.model = None

        dtm.train(samples)
        storage.save_samples(user, samples)
        storage.save_model(user, dtm.model)

        return render_template("enroll.html", done=True, count=len(samples))

    return render_template("enroll.html", done=False, count=0)

# =====================================================
# OTP (OPTIONAL)
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
# RISK API (THREAD SAFE)
# =====================================================

@app.route("/api/risk")
def api_risk():
    with _monitor_lock:
        return jsonify(_latest_risk)

# =====================================================
# START/STOP API
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
# RESET ENDPOINT
# =====================================================

@app.route("/api/reset_security", methods=["POST"])
def api_reset_security():
    stop_monitoring()
    reset_security_state()
    return jsonify({"reset": True})

# =====================================================
# ATTACK MODE ENDPOINT
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

    return jsonify({"attack_mode": _attack_mode, "level": _attack_level})

# =====================================================
# ANALYTICS / EXTRAS
# =====================================================

@app.route("/api/analytics")
def api_analytics():
    return jsonify(evaluate_far_frr(session.get("user")))


@app.route("/api/explain")
def api_explain():
    with _monitor_lock:
        feats = _latest_risk.get("features", {})
    return jsonify(explain(feats))


@app.route("/api/replay")
def api_replay():
    return jsonify(build_replay_sequence())


@app.route("/api/confidence")
def api_confidence():
    with _monitor_lock:
        return jsonify({"confidence": _latest_risk.get("confidence", 100)})


@app.route("/api/fingerprint")
def api_fingerprint():
    with _monitor_lock:
        return jsonify({"fingerprint": _latest_risk.get("fingerprint_score", 100)})


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
# USER SETTINGS (BACKGROUND COLOR)
# =====================================================

@app.route("/api/settings/color", methods=["GET"])
def api_get_color():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    return jsonify({
        "background_color": storage.get_user_color(session["user"])
    })


@app.route("/api/settings/color", methods=["POST"])
def api_set_color():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    color = data.get("color")

    if not color:
        return jsonify({"error": "Color required"}), 400

    storage.save_user_color(session["user"], color)
    return jsonify({"saved": True, "background_color": color})

# =====================================================

if __name__ == "__main__":
    app.run(debug=True, threaded=True, use_reloader=False)