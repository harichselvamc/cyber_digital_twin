"""
Behavioral CAPTCHA Module

Instead of image-based CAPTCHA, this module generates behavioral
challenges that ask the user to:
- Type a specific pattern
- Move the mouse in a specific way

Verifies identity through behavior, not image recognition.
"""

import time
import random
import string
import threading
from typing import Dict, Optional


# Challenge types and their verification logic
CHALLENGE_PHRASES = [
    "the quick brown fox jumps",
    "security is not optional",
    "verify my identity now",
    "continuous protection active",
    "behavioral twin confirmed",
    "trust but always verify",
    "digital guardian active",
    "authenticate with rhythm",
]


class BehavioralCaptcha:
    """
    Generates and verifies behavioral CAPTCHA challenges.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._active_challenges: Dict[str, Dict] = {}  # user -> challenge

    def generate_challenge(self, user: str, challenge_type: str = "typing") -> Dict:
        """
        Generate a new behavioral challenge for a user.

        Types:
        - "typing": User must type a phrase (we analyze rhythm)
        - "pattern": User must draw a mouse pattern
        """
        challenge_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))

        if challenge_type == "typing":
            phrase = random.choice(CHALLENGE_PHRASES)
            challenge = {
                "id": challenge_id,
                "type": "typing",
                "phrase": phrase,
                "created_at": time.time(),
                "expires_at": time.time() + 120,  # 2 minutes
                "verified": False,
            }
        elif challenge_type == "pattern":
            # Generate target points for mouse pattern
            points = []
            for i in range(4):
                points.append({
                    "x": random.randint(50, 350),
                    "y": random.randint(50, 250),
                    "order": i + 1,
                })
            challenge = {
                "id": challenge_id,
                "type": "pattern",
                "points": points,
                "created_at": time.time(),
                "expires_at": time.time() + 120,
                "verified": False,
            }
        else:
            return {"error": "Unknown challenge type"}

        with self._lock:
            self._active_challenges[user] = challenge

        return challenge

    def verify_typing_challenge(
        self,
        user: str,
        typed_text: str,
        keystroke_timings: list,
    ) -> Dict:
        """
        Verify a typing challenge.
        Checks:
        1. Text matches the challenge phrase
        2. Keystroke timings show human-like patterns
        """
        with self._lock:
            challenge = self._active_challenges.get(user)

        if not challenge or challenge["type"] != "typing":
            return {"passed": False, "reason": "no_active_challenge"}

        if time.time() > challenge["expires_at"]:
            return {"passed": False, "reason": "expired"}

        # Check text match (case-insensitive, strip whitespace)
        expected = challenge["phrase"].lower().strip()
        actual = typed_text.lower().strip()

        if actual != expected:
            return {"passed": False, "reason": "text_mismatch"}

        # Analyze keystroke timings for human-likeness
        if len(keystroke_timings) < 3:
            return {"passed": False, "reason": "insufficient_timing_data"}

        intervals = []
        for i in range(1, len(keystroke_timings)):
            dt = keystroke_timings[i] - keystroke_timings[i - 1]
            if dt > 0:
                intervals.append(dt)

        if not intervals:
            return {"passed": False, "reason": "no_intervals"}

        mean_interval = sum(intervals) / len(intervals)
        variance = sum((iv - mean_interval) ** 2 for iv in intervals) / len(intervals)
        std_interval = variance ** 0.5

        # Human checks:
        # 1. Mean interval should be between 50ms and 500ms
        # 2. There should be SOME variance (robots are too consistent)
        # 3. No impossibly fast intervals (< 20ms)
        human_speed = 0.02 <= mean_interval <= 0.5
        has_variance = std_interval > 0.01
        no_impossible = all(iv >= 0.02 for iv in intervals)

        passed = human_speed and has_variance and no_impossible

        with self._lock:
            if passed:
                self._active_challenges[user]["verified"] = True

        return {
            "passed": passed,
            "reason": "verified" if passed else "failed_behavioral_check",
            "metrics": {
                "mean_interval_ms": round(mean_interval * 1000, 1),
                "std_interval_ms": round(std_interval * 1000, 1),
                "human_speed": human_speed,
                "has_variance": has_variance,
                "no_impossible": no_impossible,
            },
        }

    def verify_pattern_challenge(
        self,
        user: str,
        mouse_points: list,
    ) -> Dict:
        """
        Verify a mouse pattern challenge.
        Checks that user visited target points in correct order.
        """
        with self._lock:
            challenge = self._active_challenges.get(user)

        if not challenge or challenge["type"] != "pattern":
            return {"passed": False, "reason": "no_active_challenge"}

        if time.time() > challenge["expires_at"]:
            return {"passed": False, "reason": "expired"}

        target_points = challenge["points"]

        if len(mouse_points) < len(target_points):
            return {"passed": False, "reason": "insufficient_points"}

        # Check proximity to each target point in order
        tolerance = 40  # pixels
        matched = 0
        point_idx = 0

        for mp in mouse_points:
            if point_idx >= len(target_points):
                break
            tp = target_points[point_idx]
            dist = ((mp["x"] - tp["x"]) ** 2 + (mp["y"] - tp["y"]) ** 2) ** 0.5
            if dist <= tolerance:
                matched += 1
                point_idx += 1

        passed = matched == len(target_points)

        with self._lock:
            if passed:
                self._active_challenges[user]["verified"] = True

        return {
            "passed": passed,
            "reason": "verified" if passed else "pattern_mismatch",
            "matched_points": matched,
            "total_points": len(target_points),
        }

    def get_active_challenge(self, user: str) -> Optional[Dict]:
        with self._lock:
            return self._active_challenges.get(user)

    def clear_challenge(self, user: str) -> None:
        with self._lock:
            self._active_challenges.pop(user, None)


# Global instance
behavioral_captcha = BehavioralCaptcha()
