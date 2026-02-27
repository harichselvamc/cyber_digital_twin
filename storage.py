import os
import json
import joblib
from typing import Any, Dict, List, Optional

BASE_DIR = "data"


# =====================================================
# INTERNAL HELPERS
# =====================================================

def _user_dir(user: str) -> str:
    path = os.path.join(BASE_DIR, user)
    os.makedirs(path, exist_ok=True)
    return path


def _settings_path(user: str) -> str:
    return os.path.join(_user_dir(user), "settings.json")


# =====================================================
# SAMPLES STORAGE
# =====================================================

def save_samples(user: str, samples: List[Dict[str, float]]) -> None:
    path = os.path.join(_user_dir(user), "samples.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(samples, f, indent=2)


def load_samples(user: str) -> List[Dict[str, float]]:
    path = os.path.join(_user_dir(user), "samples.json")
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# =====================================================
# MODEL STORAGE
# =====================================================

def _model_path(user: str) -> str:
    return os.path.join(_user_dir(user), "model.joblib")


def save_model(user: str, model: Any) -> None:
    path = _model_path(user)
    joblib.dump(model, path)


def load_model(user: str) -> Optional[Any]:
    path = _model_path(user)
    if os.path.exists(path):
        return joblib.load(path)
    return None


def delete_model(user: str) -> bool:
    """
    Deletes saved model so enrollment trains a fresh model.
    This is IMPORTANT after you change model.py or attacker_simulator.py,
    otherwise your app keeps using the old saved model.joblib.
    """
    path = _model_path(user)
    if os.path.exists(path):
        os.remove(path)
        print(f"[storage] Deleted old model: {path}")
        return True
    return False


# =====================================================
# USER SETTINGS (BACKGROUND COLOR)
# =====================================================

def save_user_color(user: str, color: str) -> None:
    """
    Saves background color preference per user.
    Accepts hex (#ffffff) or any valid CSS color string.
    """
    path = _settings_path(user)

    settings: Dict[str, Any] = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            settings = json.load(f)

    settings["background_color"] = color

    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)


def get_user_color(user: str) -> str:
    """
    Returns saved background color.
    Defaults to dark theme if not set.
    """
    path = _settings_path(user)

    if not os.path.exists(path):
        return "#0f172a"  # default background

    with open(path, "r", encoding="utf-8") as f:
        settings = json.load(f)

    return settings.get("background_color", "#0f172a")


def get_all_settings(user: str) -> Dict[str, Any]:
    """
    Returns full settings object (for future expansion).
    """
    path = _settings_path(user)

    if not os.path.exists(path):
        return {"background_color": "#0f172a"}

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)