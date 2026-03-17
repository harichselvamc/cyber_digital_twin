"""
Context-Aware Authentication Module

Detects location, time, and device context to adjust risk scoring.
- Unusual login time → increased risk
- New device/IP → trigger verification
- Adds an intelligent layer beyond behavioral biometrics
"""

import time
import hashlib
import threading
from typing import Dict, Optional
from dataclasses import dataclass, field


@dataclass
class DeviceFingerprint:
    ip_address: str = ""
    user_agent: str = ""
    screen_resolution: str = ""
    timezone: str = ""
    language: str = ""

    def hash(self) -> str:
        raw = f"{self.ip_address}|{self.user_agent}|{self.screen_resolution}|{self.timezone}|{self.language}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


@dataclass
class ContextProfile:
    known_devices: list = field(default_factory=list)
    known_ips: list = field(default_factory=list)
    typical_hours: list = field(default_factory=lambda: list(range(8, 22)))  # 8am-10pm default
    login_history: list = field(default_factory=list)


_user_contexts: Dict[str, ContextProfile] = {}
_lock = threading.Lock()


def get_or_create_profile(user: str) -> ContextProfile:
    with _lock:
        if user not in _user_contexts:
            _user_contexts[user] = ContextProfile()
        return _user_contexts[user]


def register_login(user: str, device: DeviceFingerprint) -> None:
    """Register a successful login to build context history."""
    profile = get_or_create_profile(user)
    with _lock:
        dev_hash = device.hash()
        if dev_hash not in profile.known_devices:
            profile.known_devices.append(dev_hash)
            # Keep last 10 known devices
            profile.known_devices = profile.known_devices[-10:]

        if device.ip_address and device.ip_address not in profile.known_ips:
            profile.known_ips.append(device.ip_address)
            profile.known_ips = profile.known_ips[-20:]

        current_hour = time.localtime().tm_hour
        profile.login_history.append({
            "hour": current_hour,
            "ts": time.time(),
            "device_hash": dev_hash,
            "ip": device.ip_address,
        })
        profile.login_history = profile.login_history[-100:]

        # Update typical hours from login history
        if len(profile.login_history) >= 5:
            hour_counts = {}
            for entry in profile.login_history:
                h = entry["hour"]
                hour_counts[h] = hour_counts.get(h, 0) + 1
            # Typical hours = hours with at least 1 login
            profile.typical_hours = sorted(hour_counts.keys())


def evaluate_context_risk(user: str, device: DeviceFingerprint) -> Dict:
    """
    Evaluate context-based risk factors.
    Returns risk adjustment and flags.
    """
    profile = get_or_create_profile(user)

    risk_boost = 0.0
    flags = []

    current_hour = time.localtime().tm_hour

    # 1. Unusual time check
    if current_hour not in profile.typical_hours:
        risk_boost += 8.0
        flags.append("unusual_time")

    # Late night / early morning (0-5 AM) extra penalty
    if current_hour in range(0, 6):
        risk_boost += 5.0
        flags.append("late_night_access")

    # 2. New device check
    dev_hash = device.hash()
    if profile.known_devices and dev_hash not in profile.known_devices:
        risk_boost += 12.0
        flags.append("new_device")

    # 3. New IP check
    if profile.known_ips and device.ip_address and device.ip_address not in profile.known_ips:
        risk_boost += 8.0
        flags.append("new_ip")

    # 4. Rapid session switching (multiple logins in short time)
    recent_logins = [
        e for e in profile.login_history
        if time.time() - e["ts"] < 300  # last 5 minutes
    ]
    if len(recent_logins) > 3:
        risk_boost += 10.0
        flags.append("rapid_logins")

    return {
        "context_risk_boost": round(risk_boost, 2),
        "flags": flags,
        "device_hash": dev_hash,
        "is_known_device": dev_hash in profile.known_devices,
        "is_known_ip": device.ip_address in profile.known_ips,
        "is_typical_hour": current_hour in profile.typical_hours,
        "current_hour": current_hour,
    }


def get_context_summary(user: str) -> Dict:
    """Get context profile summary for dashboard display."""
    profile = get_or_create_profile(user)
    return {
        "known_devices_count": len(profile.known_devices),
        "known_ips_count": len(profile.known_ips),
        "typical_hours": profile.typical_hours,
        "total_logins": len(profile.login_history),
    }
