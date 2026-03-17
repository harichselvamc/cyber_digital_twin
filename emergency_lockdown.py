"""
Emergency Lockdown Mode

Admin can:
- Lock all sessions remotely
- Lock specific user sessions
- Trigger immediate security response

Useful for:
- Security breach response
- Incident containment
"""

import time
import threading
from typing import Dict, List, Optional


class EmergencyLockdown:
    """
    Manages emergency lockdown state for the entire system
    or individual user sessions.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._global_lockdown: bool = False
        self._global_lockdown_ts: Optional[float] = None
        self._global_lockdown_reason: str = ""
        self._locked_users: Dict[str, Dict] = {}
        self._lockdown_log: List[Dict] = []

    def activate_global_lockdown(self, reason: str = "Security breach", initiated_by: str = "admin") -> Dict:
        """Lock ALL sessions immediately."""
        with self._lock:
            self._global_lockdown = True
            self._global_lockdown_ts = time.time()
            self._global_lockdown_reason = reason

            entry = {
                "ts": time.time(),
                "type": "global_lockdown",
                "action": "activate",
                "reason": reason,
                "initiated_by": initiated_by,
            }
            self._lockdown_log.append(entry)

            return {
                "status": "global_lockdown_active",
                "reason": reason,
                "ts": self._global_lockdown_ts,
            }

    def deactivate_global_lockdown(self, initiated_by: str = "admin") -> Dict:
        """Release global lockdown."""
        with self._lock:
            self._global_lockdown = False
            self._global_lockdown_ts = None
            self._global_lockdown_reason = ""

            entry = {
                "ts": time.time(),
                "type": "global_lockdown",
                "action": "deactivate",
                "initiated_by": initiated_by,
            }
            self._lockdown_log.append(entry)

            return {"status": "global_lockdown_released"}

    def lock_user(self, user: str, reason: str = "Admin action", initiated_by: str = "admin") -> Dict:
        """Lock a specific user's session."""
        with self._lock:
            self._locked_users[user] = {
                "ts": time.time(),
                "reason": reason,
                "initiated_by": initiated_by,
            }

            entry = {
                "ts": time.time(),
                "type": "user_lock",
                "action": "lock",
                "user": user,
                "reason": reason,
                "initiated_by": initiated_by,
            }
            self._lockdown_log.append(entry)

            return {
                "status": "user_locked",
                "user": user,
                "reason": reason,
            }

    def unlock_user(self, user: str, initiated_by: str = "admin") -> Dict:
        """Unlock a specific user's session."""
        with self._lock:
            self._locked_users.pop(user, None)

            entry = {
                "ts": time.time(),
                "type": "user_lock",
                "action": "unlock",
                "user": user,
                "initiated_by": initiated_by,
            }
            self._lockdown_log.append(entry)

            return {"status": "user_unlocked", "user": user}

    def is_locked(self, user: str) -> bool:
        """Check if a user is currently locked (by global or individual lock)."""
        with self._lock:
            if self._global_lockdown:
                return True
            return user in self._locked_users

    def get_lock_reason(self, user: str) -> str:
        """Get the reason for a user's lock."""
        with self._lock:
            if self._global_lockdown:
                return f"Global lockdown: {self._global_lockdown_reason}"
            if user in self._locked_users:
                return self._locked_users[user].get("reason", "Admin action")
            return ""

    def get_status(self) -> Dict:
        """Get full lockdown status."""
        with self._lock:
            return {
                "global_lockdown": self._global_lockdown,
                "global_reason": self._global_lockdown_reason,
                "global_lockdown_ts": self._global_lockdown_ts,
                "locked_users": dict(self._locked_users),
                "locked_user_count": len(self._locked_users),
            }

    def get_log(self) -> List[Dict]:
        """Get lockdown audit log."""
        with self._lock:
            return list(self._lockdown_log)

    def reset(self) -> None:
        """Reset all lockdown state."""
        with self._lock:
            self._global_lockdown = False
            self._global_lockdown_ts = None
            self._global_lockdown_reason = ""
            self._locked_users.clear()


# Global instance
emergency_lockdown = EmergencyLockdown()
