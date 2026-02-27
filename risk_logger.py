import os
import json
import time
import threading
from typing import Any, Dict, List

LOG_FILE = os.path.join("data", "risk_log.json")
_LOCK = threading.Lock()


def _ensure_dir():
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)


def _safe_load() -> List[Dict[str, Any]]:
    """
    Load JSON safely.
    If file is missing -> []
    If file is corrupted -> backup + []
    """
    _ensure_dir()

    if not os.path.exists(LOG_FILE):
        return []

    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        # Backup corrupted file and reset
        backup = LOG_FILE + f".corrupt_{int(time.time())}"
        try:
            os.replace(LOG_FILE, backup)
        except Exception:
            pass
        return []
    except Exception:
        return []


def _atomic_write(data: List[Dict[str, Any]]) -> None:
    """
    Atomic write: write to temp file then replace.
    Prevents partial writes that corrupt JSON.
    """
    _ensure_dir()
    tmp = LOG_FILE + ".tmp"

    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    os.replace(tmp, LOG_FILE)


def _ensure_file_initialized() -> None:
    """
    Ensure file exists and contains valid JSON list.
    """
    _ensure_dir()
    if not os.path.exists(LOG_FILE):
        _atomic_write([])


def log_risk(entry: dict) -> None:
    """
    Thread-safe append of a risk entry.
    """
    with _LOCK:
        _ensure_file_initialized()
        data = _safe_load()

        data.append({
            "ts": float(entry.get("ts", time.time())),
            "risk_score": float(entry.get("risk_score", 0.0)),
            "level": str(entry.get("level", "LOW")),
            "action": str(entry.get("action", "ALLOW")),
        })

        # keep last 1000 records (same behavior as before)
        data = data[-1000:]

        _atomic_write(data)


def load_history() -> List[Dict[str, Any]]:
    """
    Thread-safe load of risk history.
    """
    with _LOCK:
        _ensure_file_initialized()
        return _safe_load()