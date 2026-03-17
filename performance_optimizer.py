"""
Energy & Performance Optimizer

Reduces monitoring frequency when:
- System is idle (no user activity)
- Risk is consistently low

Ensures:
- Low CPU usage
- Battery efficiency on laptops

Also handles Screen Activity Analysis (unusual app switching detection).
"""

import time
import threading
from typing import Dict, Optional
from collections import deque


class PerformanceOptimizer:
    """
    Adaptive monitoring frequency based on system state.
    """

    def __init__(
        self,
        base_interval: float = 1.0,
        idle_interval: float = 5.0,
        active_interval: float = 0.5,
        idle_timeout: float = 30.0,
    ):
        self.base_interval = base_interval
        self.idle_interval = idle_interval
        self.active_interval = active_interval
        self.idle_timeout = idle_timeout

        self._lock = threading.Lock()
        self._last_activity_ts: float = time.time()
        self._current_interval: float = base_interval
        self._is_idle: bool = False
        self._risk_history: deque = deque(maxlen=20)
        self._stats = {
            "cycles_saved": 0,
            "total_cycles": 0,
            "idle_time_total": 0.0,
        }

    def report_activity(self) -> None:
        """Call when user activity is detected."""
        with self._lock:
            self._last_activity_ts = time.time()
            self._is_idle = False

    def report_risk(self, risk_score: float) -> None:
        """Feed risk score to optimize polling frequency."""
        with self._lock:
            self._risk_history.append(risk_score)

    def get_optimal_interval(self) -> float:
        """
        Calculate optimal polling interval based on current state.
        """
        with self._lock:
            now = time.time()
            time_since_activity = now - self._last_activity_ts
            self._stats["total_cycles"] += 1

            # Check idle state
            if time_since_activity > self.idle_timeout:
                self._is_idle = True
                self._stats["cycles_saved"] += 1
                self._current_interval = self.idle_interval
                return self.idle_interval

            # Check if risk is elevated
            if self._risk_history:
                avg_risk = sum(self._risk_history) / len(self._risk_history)
                max_recent_risk = max(self._risk_history)

                if max_recent_risk > 60 or avg_risk > 40:
                    # High alert: faster polling
                    self._current_interval = self.active_interval
                    return self.active_interval

                if avg_risk < 15 and max_recent_risk < 25:
                    # Very low risk: can slow down slightly
                    self._current_interval = self.base_interval * 1.5
                    self._stats["cycles_saved"] += 1
                    return self.base_interval * 1.5

            self._current_interval = self.base_interval
            return self.base_interval

    def is_idle(self) -> bool:
        with self._lock:
            return self._is_idle

    def get_stats(self) -> Dict:
        with self._lock:
            total = self._stats["total_cycles"]
            saved = self._stats["cycles_saved"]
            return {
                "total_cycles": total,
                "cycles_saved": saved,
                "efficiency_pct": round((saved / total * 100) if total > 0 else 0, 1),
                "current_interval": round(self._current_interval, 2),
                "is_idle": self._is_idle,
            }

    def reset(self) -> None:
        with self._lock:
            self._last_activity_ts = time.time()
            self._is_idle = False
            self._risk_history.clear()
            self._stats = {
                "cycles_saved": 0,
                "total_cycles": 0,
                "idle_time_total": 0.0,
            }


class ScreenActivityAnalyzer:
    """
    Detects unusual screen activity patterns:
    - Rapid window switching
    - Unusual app patterns
    """

    def __init__(self, switch_threshold: int = 10, window_seconds: float = 10.0):
        self.switch_threshold = switch_threshold
        self.window_seconds = window_seconds

        self._lock = threading.Lock()
        self._switches: deque = deque(maxlen=200)
        self._alerts: deque = deque(maxlen=50)

    def record_switch(self, from_app: str = "", to_app: str = "") -> Optional[Dict]:
        """Record a window/app switch event."""
        now = time.time()
        with self._lock:
            self._switches.append({
                "ts": now,
                "from": from_app,
                "to": to_app,
            })

            # Count switches in recent window
            recent = [s for s in self._switches if now - s["ts"] < self.window_seconds]
            rate = len(recent)

            if rate >= self.switch_threshold:
                alert = {
                    "ts": now,
                    "type": "rapid_switching",
                    "switch_rate": rate,
                    "window_seconds": self.window_seconds,
                    "risk_boost": min(15.0, rate * 1.5),
                }
                self._alerts.append(alert)
                return alert

            return None

    def get_switch_rate(self) -> float:
        """Get current switch rate per window."""
        now = time.time()
        with self._lock:
            recent = [s for s in self._switches if now - s["ts"] < self.window_seconds]
            return len(recent)

    def get_alerts(self) -> list:
        with self._lock:
            return list(self._alerts)

    def get_risk_boost(self) -> float:
        """Get current risk boost from screen activity."""
        rate = self.get_switch_rate()
        if rate >= self.switch_threshold:
            return min(15.0, rate * 1.5)
        return 0.0


# Global instances
performance_optimizer = PerformanceOptimizer()
screen_analyzer = ScreenActivityAnalyzer()
