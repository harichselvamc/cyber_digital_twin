
import random
import time
from typing import Dict

FEATURES = [
    "key_rate",
    "iki_mean",
    "iki_std",
    "hold_mean",
    "hold_std",
    "mouse_speed_mean",
    "mouse_speed_std",
    "click_rate",
]


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def generate_attacker_features(level: int = 3, start_ts: float | None = None) -> Dict[str, float]:
    """
    Level-based attacker features:
      level 1: mild anomaly (often triggers STEP_UP)
      level 2: medium anomaly
      level 3: strong anomaly (should trigger BLOCK quickly)

    start_ts: if provided, features gradually escalate as time passes (more realistic attack).
    """

    level = int(level)
    if level < 1:
        level = 1
    if level > 3:
        level = 3

    # Escalation factor increases over time (0 -> 1.0)
    if start_ts is None:
        esc = 1.0
    else:
        esc = _clamp((time.time() - start_ts) / 15.0, 0.0, 1.0)  # reaches max in ~15s

    # Scale by level
    # L1 = 0.4..0.7 effect, L2 = 0.7..0.9, L3 = 0.9..1.2
    if level == 1:
        strength = 0.45 + 0.25 * esc
    elif level == 2:
        strength = 0.75 + 0.20 * esc
    else:
        strength = 1.00 + 0.20 * esc


    fast_or_slow = random.choice(["fast", "slow"])

    if fast_or_slow == "fast":
        key_rate = random.uniform(10, 25) * strength
        iki_mean = random.uniform(0.01, 0.04) / max(strength, 0.3)
    else:
        key_rate = random.uniform(0.1, 2.0) / max(strength, 0.3)
        iki_mean = random.uniform(0.25, 0.8) * strength

    iki_std = random.uniform(0.25, 1.2) * strength

    
    if random.random() < 0.5:
        hold_mean = random.uniform(0.005, 0.02) / max(strength, 0.3)
    else:
        hold_mean = random.uniform(0.25, 0.7) * strength

    hold_std = random.uniform(0.15, 0.9) * strength

    mouse_speed_mean = random.uniform(2500, 9000) * strength
    mouse_speed_std = random.uniform(900, 3500) * strength

    click_rate = random.uniform(2.5, 12.0) * strength

    # Level 1 should be "less extreme" (to simulate stealth attacker)
    if level == 1:
        mouse_speed_mean = random.uniform(1200, 3500) * strength
        mouse_speed_std = random.uniform(300, 1200) * strength
        click_rate = random.uniform(0.8, 4.0) * strength

        
        iki_std = random.uniform(0.12, 0.5) * strength
        hold_std = random.uniform(0.08, 0.4) * strength

    return {
        "key_rate": float(_clamp(key_rate, 0.0, 50.0)),
        "iki_mean": float(_clamp(iki_mean, 0.0, 2.0)),
        "iki_std": float(_clamp(iki_std, 0.0, 3.0)),
        "hold_mean": float(_clamp(hold_mean, 0.0, 2.0)),
        "hold_std": float(_clamp(hold_std, 0.0, 3.0)),
        "mouse_speed_mean": float(_clamp(mouse_speed_mean, 0.0, 20000.0)),
        "mouse_speed_std": float(_clamp(mouse_speed_std, 0.0, 20000.0)),
        "click_rate": float(_clamp(click_rate, 0.0, 30.0)),
    }
