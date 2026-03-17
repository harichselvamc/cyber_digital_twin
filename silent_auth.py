"""
Silent Authentication Mode

No interruption to user. System silently:
- Monitors behavioral patterns
- Logs suspicious activity
- Flags anomalies

Only acts when risk crosses defined threshold.
Also supports Gamified Security Awareness notifications.
"""

import time
import threading
from typing import Dict, List, Optional
from collections import deque


class SilentAuthMode:
    """
    Silent authentication operates in the background without
    user interruption. It accumulates observations and only
    surfaces alerts when confidence in an anomaly is very high.
    """

    def __init__(
        self,
        silent_threshold: float = 75.0,
        notification_cooldown: float = 60.0,
    ):
        self.enabled = False
        self.silent_threshold = silent_threshold
        self.notification_cooldown = notification_cooldown

        self._lock = threading.Lock()
        self._silent_log: deque = deque(maxlen=500)
        self._notifications: deque = deque(maxlen=50)
        self._last_notification_ts: float = 0.0
        self._session_stats = {
            "total_observations": 0,
            "silent_flags": 0,
            "escalations": 0,
        }

    def enable(self) -> None:
        with self._lock:
            self.enabled = True

    def disable(self) -> None:
        with self._lock:
            self.enabled = False

    def observe(self, risk_data: Dict) -> Optional[Dict]:
        """
        Silently observe a risk data point.
        Returns a notification dict only if threshold is crossed.
        """
        with self._lock:
            if not self.enabled:
                return None

            self._session_stats["total_observations"] += 1

            entry = {
                "ts": time.time(),
                "risk_score": risk_data.get("risk_score", 0),
                "level": risk_data.get("level", "LOW"),
                "action": risk_data.get("action", "ALLOW"),
                "silently_flagged": False,
            }

            risk = risk_data.get("risk_score", 0)

            if risk >= self.silent_threshold:
                entry["silently_flagged"] = True
                self._session_stats["silent_flags"] += 1

                # Check cooldown before generating notification
                now = time.time()
                if now - self._last_notification_ts >= self.notification_cooldown:
                    self._last_notification_ts = now
                    self._session_stats["escalations"] += 1

                    notification = self._generate_notification(risk_data)
                    self._notifications.append(notification)
                    self._silent_log.append(entry)
                    return notification

            self._silent_log.append(entry)
            return None

    def _generate_notification(self, risk_data: Dict) -> Dict:
        """Generate a gamified security awareness notification."""
        risk = risk_data.get("risk_score", 0)

        if risk >= 90:
            message = "Critical behavioral deviation detected. Your session security needs immediate attention."
            severity = "critical"
            icon = "shield-exclamation"
        elif risk >= 75:
            message = "Your typing behavior changed significantly. Consider re-verifying your identity."
            severity = "warning"
            icon = "triangle-exclamation"
        else:
            message = "Minor behavioral shift noticed. Stay consistent for optimal security."
            severity = "info"
            icon = "circle-info"

        return {
            "ts": time.time(),
            "message": message,
            "severity": severity,
            "icon": icon,
            "risk_score": round(risk, 1),
            "action_suggested": risk_data.get("action", "ALLOW"),
        }

    def get_silent_log(self) -> List[Dict]:
        with self._lock:
            return list(self._silent_log)

    def get_notifications(self) -> List[Dict]:
        with self._lock:
            return list(self._notifications)

    def get_stats(self) -> Dict:
        with self._lock:
            return dict(self._session_stats)

    def reset(self) -> None:
        with self._lock:
            self._silent_log.clear()
            self._notifications.clear()
            self._last_notification_ts = 0.0
            self._session_stats = {
                "total_observations": 0,
                "silent_flags": 0,
                "escalations": 0,
            }


# Global instance
silent_auth = SilentAuthMode()
