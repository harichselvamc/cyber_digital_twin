import time
import threading
from collections import deque
from dataclasses import dataclass
from typing import Dict, Optional, List

from pynput import keyboard, mouse


@dataclass
class BehaviorSnapshot:
    ts: float
    features: Dict[str, float]


class BehaviorCollector:
    """
    Collects behavioral biometrics in windows:
      - key press intervals (IKI)
      - key hold times
      - mouse speed stats
      - mouse click rate
    Produces feature vectors suitable for anomaly detection.
    """
    def __init__(self, window_seconds: float = 10.0, max_events: int = 5000):
        self.window_seconds = window_seconds
        self._lock = threading.Lock()

        # Keyboard tracking
        self._key_down_time: Dict[str, float] = {}
        self._key_press_ts: deque = deque(maxlen=max_events)   # timestamps of key presses
        self._key_hold_times: deque = deque(maxlen=max_events) # hold durations

        # Mouse tracking
        self._mouse_moves: deque = deque(maxlen=max_events)  # (ts, x, y)
        self._mouse_click_ts: deque = deque(maxlen=max_events)

        self._kb_listener: Optional[keyboard.Listener] = None
        self._mouse_listener: Optional[mouse.Listener] = None
        self._running = False

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True

        self._kb_listener = keyboard.Listener(on_press=self._on_key_press, on_release=self._on_key_release)
        self._mouse_listener = mouse.Listener(on_move=self._on_mouse_move, on_click=self._on_mouse_click)

        self._kb_listener.start()
        self._mouse_listener.start()

    def stop(self) -> None:
        with self._lock:
            self._running = False
        if self._kb_listener:
            self._kb_listener.stop()
        if self._mouse_listener:
            self._mouse_listener.stop()

    def _on_key_press(self, key) -> None:
        ts = time.time()
        k = self._key_to_str(key)
        with self._lock:
            self._key_press_ts.append(ts)
            # record first down time if not already
            if k not in self._key_down_time:
                self._key_down_time[k] = ts

    def _on_key_release(self, key) -> None:
        ts = time.time()
        k = self._key_to_str(key)
        with self._lock:
            if k in self._key_down_time:
                hold = ts - self._key_down_time.pop(k)
                if 0.0 < hold < 5.0:  # basic sanity clamp
                    self._key_hold_times.append(hold)

    def _on_mouse_move(self, x, y) -> None:
        ts = time.time()
        with self._lock:
            self._mouse_moves.append((ts, x, y))

    def _on_mouse_click(self, x, y, button, pressed) -> None:
        if not pressed:
            return
        ts = time.time()
        with self._lock:
            self._mouse_click_ts.append(ts)

    @staticmethod
    def _key_to_str(key) -> str:
        try:
            return key.char if key.char else str(key)
        except Exception:
            return str(key)

    def snapshot(self) -> BehaviorSnapshot:
        """
        Compute features from the last window_seconds.
        """
        now = time.time()
        start = now - self.window_seconds

        with self._lock:
            key_ts = [t for t in self._key_press_ts if t >= start]
            holds = [h for h in self._key_hold_times]  # holds are durations; keep recent-ish by size

            moves = [m for m in self._mouse_moves if m[0] >= start]
            clicks = [t for t in self._mouse_click_ts if t >= start]

        # Keyboard features
        key_count = len(key_ts)
        iki_mean, iki_std = self._interval_stats(key_ts)

        hold_mean = float(sum(holds) / len(holds)) if holds else 0.0
        hold_std = self._std(holds) if len(holds) > 1 else 0.0

        # Mouse features
        mouse_speed_mean, mouse_speed_std = self._mouse_speed_stats(moves)
        click_rate = len(clicks) / max(self.window_seconds, 1e-6)

        features = {
            "key_rate": key_count / max(self.window_seconds, 1e-6),
            "iki_mean": iki_mean,
            "iki_std": iki_std,
            "hold_mean": hold_mean,
            "hold_std": hold_std,
            "mouse_speed_mean": mouse_speed_mean,
            "mouse_speed_std": mouse_speed_std,
            "click_rate": click_rate,
        }
        return BehaviorSnapshot(ts=now, features=features)

    @staticmethod
    def _interval_stats(timestamps: List[float]) -> (float, float):
        if len(timestamps) < 2:
            return 0.0, 0.0
        intervals = [timestamps[i] - timestamps[i - 1] for i in range(1, len(timestamps))]
        mean = float(sum(intervals) / len(intervals))
        std = BehaviorCollector._std(intervals) if len(intervals) > 1 else 0.0
        return mean, std

    @staticmethod
    def _mouse_speed_stats(moves: List[tuple]) -> (float, float):
        if len(moves) < 2:
            return 0.0, 0.0
        speeds = []
        for i in range(1, len(moves)):
            t0, x0, y0 = moves[i - 1]
            t1, x1, y1 = moves[i]
            dt = t1 - t0
            if dt <= 0:
                continue
            dist = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
            speeds.append(dist / dt)
        if not speeds:
            return 0.0, 0.0
        mean = float(sum(speeds) / len(speeds))
        std = BehaviorCollector._std(speeds) if len(speeds) > 1 else 0.0
        return mean, std

    @staticmethod
    def _std(vals: List[float]) -> float:
        if len(vals) < 2:
            return 0.0
        m = sum(vals) / len(vals)
        var = sum((v - m) ** 2 for v in vals) / (len(vals) - 1)
        return float(var ** 0.5)
