
import os
import json
import time

LOG_FILE = "data/risk_log.json"


def _ensure_file():
    os.makedirs("data", exist_ok=True)
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            json.dump([], f)


def log_risk(entry: dict):
    _ensure_file()

    with open(LOG_FILE, "r") as f:
        data = json.load(f)

    data.append({
        "ts": time.time(),
        "risk_score": entry["risk_score"],
        "level": entry["level"],
        "action": entry["action"],
    })

    # keep last 1000 records
    data = data[-1000:]

    with open(LOG_FILE, "w") as f:
        json.dump(data, f, indent=2)


def load_history():
    _ensure_file()
    with open(LOG_FILE, "r") as f:
        return json.load(f)
