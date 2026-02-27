import random
import time
import math
from typing import Dict, Optional


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


def generate_attacker_features(level: int = 3, start_ts: Optional[float] = None) -> Dict[str, float]:
    """
    Improved attacker simulation.
    Goal: Level 3 should be consistently flagged as anomalous by IsolationForest.

    Strategy:
      - L1: mild drift (stealth)
      - L2: moderate anomaly
      - L3: strong anomaly by breaking human coupling constraints + teleport/freeze bursts
    """

    level = int(level)
    level = 1 if level < 1 else (3 if level > 3 else level)

    now = time.time()
    if start_ts is None:
        start_ts = now

    t = now - start_ts

    # Faster ramp (not used for forced lock, only for increasing anomaly characteristics)
    esc = _clamp(t / 5.0, 0.0, 1.0)

    # Separation
    if level == 1:
        strength = 0.25 + 0.30 * esc
    elif level == 2:
        strength = 0.75 + 0.45 * esc
    else:
        strength = 1.40 + 0.85 * esc  # stronger than before

    # Multi-frequency non-human oscillation
    wave = (
        1.0
        + 0.65 * math.sin(t * 3.3)
        + 0.45 * math.sin(t * 7.9)
        + 0.25 * math.sin(t * 14.7)
    )
    wave = _clamp(wave, 0.20, 2.60)

    # Random jitter helper
    def jitter(scale: float) -> float:
        return random.uniform(-scale, scale)

    # Attack events: burst + freeze + teleport
    # Level 3 triggers these more often
    burst_prob = 0.05 if level == 1 else (0.12 if level == 2 else 0.28)
    freeze_prob = 0.03 if level == 1 else (0.06 if level == 2 else 0.18)
    teleport_prob = 0.02 if level == 1 else (0.06 if level == 2 else 0.22)

    burst = 1.0 + (random.uniform(1.0, 3.5) if random.random() < burst_prob else 0.0)
    freeze = (random.uniform(0.03, 0.20) if random.random() < freeze_prob else 1.0)
    teleport = (random.uniform(1.8, 4.0) if random.random() < teleport_prob else 1.0)

    # Choose style (Level 3 biased hard toward "impossible coupling")
    if level == 3:
        style = random.choices(
            ["impossible_fast", "impossible_slow", "teleport_clicker", "mixed_inconsistent"],
            weights=[0.35, 0.20, 0.25, 0.20],
            k=1
        )[0]
    elif level == 2:
        style = random.choices(
            ["fast", "slow", "jerky", "mixed_inconsistent"],
            weights=[0.30, 0.30, 0.20, 0.20],
            k=1
        )[0]
    else:
        style = random.choices(
            ["sloppy_human", "fast", "slow"],
            weights=[0.45, 0.30, 0.25],
            k=1
        )[0]

    # --------------------------
    # Generate base features
    # --------------------------
    if style == "impossible_fast":
        # Human coupling broken:
        # absurd key rate + not-absurdly-low IKI mean (contradiction)
        key_rate = random.uniform(30, 70) * strength * burst
        iki_mean = random.uniform(0.15, 0.60) * strength * wave  # too large for that key_rate
        iki_std = random.uniform(2.5, 5.0) * strength * wave     # extremely unstable

        hold_mean = random.uniform(0.25, 0.90) * strength * wave  # too long for fast keys
        hold_std = random.uniform(2.0, 5.0) * strength * wave

        mouse_speed_mean = random.uniform(6000, 20000) * strength * teleport * burst
        mouse_speed_std = random.uniform(9000, 25000) * strength * teleport * burst

        click_rate = random.uniform(15, 40) * strength * burst

    elif style == "impossible_slow":
        # Very slow keys but very high click/mouse chaos (another contradiction)
        key_rate = random.uniform(0.02, 0.8) * freeze
        iki_mean = random.uniform(1.0, 2.0) * strength * wave
        iki_std = random.uniform(2.0, 5.0) * strength * wave

        hold_mean = random.uniform(0.8, 2.0) * strength * wave
        hold_std = random.uniform(2.0, 5.0) * strength * wave

        mouse_speed_mean = random.uniform(8000, 24000) * strength * teleport * burst
        mouse_speed_std = random.uniform(10000, 25000) * strength * teleport * burst
        click_rate = random.uniform(10, 35) * strength * burst  # too high for slow typing

    elif style == "teleport_clicker":
        # Mouse teleporting + clicking bursts (macro / bot)
        key_rate = random.uniform(4, 18) * strength * wave
        iki_mean = random.uniform(0.05, 0.35) * strength * wave
        iki_std = random.uniform(1.8, 5.0) * strength * wave * burst

        hold_mean = random.uniform(0.02, 0.25) * strength * wave
        hold_std = random.uniform(1.8, 5.0) * strength * wave * burst

        mouse_speed_mean = random.uniform(12000, 25000) * strength * teleport * burst
        mouse_speed_std = random.uniform(14000, 25000) * strength * teleport * burst

        click_rate = random.uniform(18, 40) * strength * burst

    elif style == "mixed_inconsistent":
        # Break correlations strongly but not as extreme as impossible_* styles
        key_rate = random.uniform(18, 60) * strength * burst
        iki_mean = random.uniform(0.10, 0.75) * strength * wave
        iki_std = random.uniform(1.8, 5.0) * strength * wave

        hold_mean = random.uniform(0.15, 1.20) * strength * wave
        hold_std = random.uniform(1.6, 5.0) * strength * wave

        mouse_speed_mean = random.uniform(300, 25000) * strength * (1.0 + abs(jitter(1.0))) * teleport
        mouse_speed_std = random.uniform(6000, 25000) * strength * teleport * burst

        click_rate = random.uniform(0.2, 40) * strength * (1.0 + abs(jitter(0.9))) * burst

    elif style == "fast":
        key_rate = random.uniform(14, 40) * strength * wave * burst
        iki_mean = random.uniform(0.003, 0.03) / max(strength, 0.35) / max(wave, 0.55)
        iki_std = random.uniform(0.6, 2.5) * strength * wave

        hold_mean = random.uniform(0.003, 0.02) / max(strength, 0.35)
        hold_std = random.uniform(0.6, 2.2) * strength * wave

        mouse_speed_mean = random.uniform(4000, 18000) * strength * wave * burst
        mouse_speed_std = random.uniform(2500, 12000) * strength * wave * burst

        click_rate = random.uniform(6.0, 22.0) * strength * wave * burst

    elif style == "slow":
        key_rate = random.uniform(0.05, 1.5) / max(strength, 0.45) * freeze
        iki_mean = random.uniform(0.45, 1.60) * strength * wave
        iki_std = random.uniform(0.9, 3.6) * strength * wave * burst

        hold_mean = random.uniform(0.35, 1.25) * strength * wave
        hold_std = random.uniform(0.9, 3.2) * strength * wave * burst

        mouse_speed_mean = random.uniform(200, 3000) * strength * wave * freeze
        mouse_speed_std = random.uniform(1200, 9000) * strength * wave * burst

        click_rate = random.uniform(0.1, 2.8) * strength * wave * freeze

    else:  # sloppy_human
        key_rate = random.uniform(2.0, 10.0) * (0.7 + 0.6 * esc) * wave
        iki_mean = random.uniform(0.08, 0.25) * (0.8 + 0.5 * esc) * wave
        iki_std = random.uniform(0.25, 1.10) * (0.8 + 0.5 * esc) * wave

        hold_mean = random.uniform(0.04, 0.18) * (0.8 + 0.5 * esc) * wave
        hold_std = random.uniform(0.20, 0.95) * (0.8 + 0.5 * esc) * wave

        mouse_speed_mean = random.uniform(500, 5000) * (0.8 + 0.5 * esc) * wave
        mouse_speed_std = random.uniform(300, 2500) * (0.8 + 0.5 * esc) * wave

        click_rate = random.uniform(0.5, 5.0) * (0.8 + 0.5 * esc) * wave

    # Final jitter
    key_rate *= (1.0 + jitter(0.06))
    iki_mean *= (1.0 + jitter(0.10))
    iki_std *= (1.0 + jitter(0.12))
    hold_mean *= (1.0 + jitter(0.10))
    hold_std *= (1.0 + jitter(0.12))
    mouse_speed_mean *= (1.0 + jitter(0.10))
    mouse_speed_std *= (1.0 + jitter(0.12))
    click_rate *= (1.0 + jitter(0.12))

    # Level 1 clamp (stealth)
    if level == 1:
        key_rate = _clamp(key_rate, 0.0, 12.0)
        click_rate = _clamp(click_rate, 0.0, 6.0)
        mouse_speed_mean = _clamp(mouse_speed_mean, 0.0, 6500.0)
        mouse_speed_std = _clamp(mouse_speed_std, 0.0, 3500.0)
        iki_std = _clamp(iki_std, 0.0, 1.3)
        hold_std = _clamp(hold_std, 0.0, 1.2)

    return {
        "key_rate": float(_clamp(key_rate, 0.0, 70.0)),
        "iki_mean": float(_clamp(iki_mean, 0.0, 2.0)),
        "iki_std": float(_clamp(iki_std, 0.0, 5.0)),
        "hold_mean": float(_clamp(hold_mean, 0.0, 2.0)),
        "hold_std": float(_clamp(hold_std, 0.0, 5.0)),
        "mouse_speed_mean": float(_clamp(mouse_speed_mean, 0.0, 25000.0)),
        "mouse_speed_std": float(_clamp(mouse_speed_std, 0.0, 25000.0)),
        "click_rate": float(_clamp(click_rate, 0.0, 40.0)),
    }