"""
Behavioral Drift Detection Module

Detects gradual behavior changes over time so the system
can adapt without triggering false alarms.

Uses a sliding window approach to compare recent behavior
against the enrolled baseline, tracking drift magnitude
and velocity.
"""

import time
import threading
import math
from typing import Dict, List, Optional
from collections import deque


FEATURE_ORDER = [
    "key_rate",
    "iki_mean",
    "iki_std",
    "hold_mean",
    "hold_std",
    "mouse_speed_mean",
    "mouse_speed_std",
    "click_rate",
]


class DriftDetector:
    """
    Tracks behavioral drift by maintaining a sliding window of
    recent feature observations and comparing against baseline.
    """

    def __init__(
        self,
        window_size: int = 50,
        drift_threshold: float = 0.35,
        alarm_threshold: float = 0.65,
    ):
        self.window_size = window_size
        self.drift_threshold = drift_threshold
        self.alarm_threshold = alarm_threshold

        self._lock = threading.Lock()
        self._baseline_mean: Optional[Dict[str, float]] = None
        self._baseline_std: Optional[Dict[str, float]] = None
        self._recent_window: deque = deque(maxlen=window_size)
        self._drift_history: deque = deque(maxlen=200)

    def set_baseline(self, samples: List[Dict[str, float]]) -> None:
        """Set baseline from enrollment samples."""
        if not samples:
            return

        means = {}
        stds = {}

        for feat in FEATURE_ORDER:
            values = [s.get(feat, 0.0) for s in samples]
            n = len(values)
            if n == 0:
                means[feat] = 0.0
                stds[feat] = 1.0
                continue
            m = sum(values) / n
            if n > 1:
                var = sum((v - m) ** 2 for v in values) / (n - 1)
                s = math.sqrt(var)
            else:
                s = 1.0
            means[feat] = m
            stds[feat] = max(s, 1e-6)

        with self._lock:
            self._baseline_mean = means
            self._baseline_std = stds

    def observe(self, features: Dict[str, float]) -> None:
        """Add a new observation to the sliding window."""
        with self._lock:
            self._recent_window.append({
                "features": features,
                "ts": time.time(),
            })

    def compute_drift(self) -> Dict:
        """
        Compute drift metrics between recent behavior and baseline.
        Returns drift magnitude per feature and overall drift score.
        """
        with self._lock:
            if not self._baseline_mean or len(self._recent_window) < 5:
                return {
                    "overall_drift": 0.0,
                    "feature_drift": {},
                    "status": "insufficient_data",
                    "is_drifting": False,
                    "is_alarm": False,
                }

            # Compute recent window means
            recent_means = {}
            for feat in FEATURE_ORDER:
                vals = [obs["features"].get(feat, 0.0) for obs in self._recent_window]
                recent_means[feat] = sum(vals) / len(vals)

            # Z-score based drift per feature
            feature_drift = {}
            for feat in FEATURE_ORDER:
                z = abs(recent_means[feat] - self._baseline_mean[feat]) / self._baseline_std[feat]
                feature_drift[feat] = round(z, 4)

            overall = sum(feature_drift.values()) / len(feature_drift)
            overall = round(overall, 4)

            is_drifting = overall > self.drift_threshold
            is_alarm = overall > self.alarm_threshold

            status = "stable"
            if is_alarm:
                status = "alarm"
            elif is_drifting:
                status = "drifting"

            result = {
                "overall_drift": overall,
                "feature_drift": feature_drift,
                "status": status,
                "is_drifting": is_drifting,
                "is_alarm": is_alarm,
                "window_size": len(self._recent_window),
            }

            self._drift_history.append({
                "ts": time.time(),
                "overall_drift": overall,
                "status": status,
            })

            return result

    def get_drift_history(self) -> List[Dict]:
        """Return recent drift measurements for charting."""
        with self._lock:
            return list(self._drift_history)

    def should_retrain(self) -> bool:
        """
        Adaptive learning rate: recommend retraining only when
        drift is gradual and consistent (not attack-like spikes).
        """
        with self._lock:
            if len(self._drift_history) < 10:
                return False

            recent = list(self._drift_history)[-10:]
            drifts = [d["overall_drift"] for d in recent]

            avg_drift = sum(drifts) / len(drifts)
            max_drift = max(drifts)

            # Retrain if: consistent moderate drift but not extreme spikes
            # (extreme spikes are likely attacks, not natural drift)
            if self.drift_threshold < avg_drift < self.alarm_threshold and max_drift < self.alarm_threshold * 1.5:
                return True

            return False


# Global instance
drift_detector = DriftDetector()
