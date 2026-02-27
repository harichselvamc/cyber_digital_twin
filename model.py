from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
from sklearn.ensemble import IsolationForest


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


def features_to_vector(feat: Dict[str, float]) -> np.ndarray:
    return np.array([float(feat.get(k, 0.0)) for k in FEATURE_ORDER], dtype=np.float64)


@dataclass
class RiskResult:
    risk_score: float     # 0..100 (final score used for action)
    level: str            # LOW / MEDIUM / HIGH
    action: str           # ALLOW / STEP_UP / BLOCK
    anomaly_score: float  # decision_function; higher=more normal


class DigitalTwinModel:
    """
    Digital Twin anomaly model (hardened):
    - normalize from enrollment mean/std
    - IsolationForest anomaly score
    - risk mapping + EMA for UI
    - persistence/momentum so sustained attacks reliably become BLOCK
    - extra "coupling-break" penalty to detect non-human inconsistent patterns
    """

    def __init__(
        self,
        contamination: float = 0.03,         # HARDENED: less forgiving than 0.10
        low_threshold: float = 35.0,
        high_threshold: float = 70.0,
        random_state: int = 42,
        score_scale: float = 26.0,           # HARDENED: stronger separation
        outlier_boost: float = 35.0,         # HARDENED: stronger outlier penalty
        ema_alpha: float = 0.55,             # faster response while still smooth

        momentum_alpha: float = 0.25,        # grows faster on suspicious behavior
        momentum_decay: float = 0.90,        # decays slower (keeps memory)
        outlier_strikes_block: int = 2,      # BLOCK faster on consecutive outliers
        high_risk_strikes_block: int = 2,    # BLOCK faster on consecutive high-risk
        high_risk_gate: float = 78.0,        # slightly lower gate so momentum kicks in earlier
        bypass_smoothing_gate: float = 80.0  # bypass EMA sooner if raw risk is huge
    ):
        self.model: Optional[IsolationForest] = None
        self.mean_: Optional[np.ndarray] = None
        self.std_: Optional[np.ndarray] = None

        self.contamination = float(contamination)
        self.low_threshold = float(low_threshold)
        self.high_threshold = float(high_threshold)
        self.random_state = int(random_state)

        self.score_scale = float(score_scale)
        self.outlier_boost = float(outlier_boost)
        self.ema_alpha = float(ema_alpha)

        self._risk_ema: Optional[float] = None

        self.momentum_alpha = float(momentum_alpha)
        self.momentum_decay = float(momentum_decay)
        self._momentum: float = 0.0

        self.outlier_strikes_block = int(outlier_strikes_block)
        self.high_risk_strikes_block = int(high_risk_strikes_block)
        self.high_risk_gate = float(high_risk_gate)
        self.bypass_smoothing_gate = float(bypass_smoothing_gate)

        self._outlier_streak: int = 0
        self._highrisk_streak: int = 0

    # -------------------------
    # Training
    # -------------------------
    def train(self, samples: List[Dict[str, float]]) -> None:
        if not samples:
            self.model = None
            self.mean_ = None
            self.std_ = None
            self._risk_ema = None
            self._momentum = 0.0
            self._outlier_streak = 0
            self._highrisk_streak = 0
            return

        X = np.vstack([features_to_vector(s) for s in samples])

        self.mean_ = X.mean(axis=0)
        self.std_ = X.std(axis=0)
        self.std_ = np.where(self.std_ < 1e-6, 1.0, self.std_)

        Xn = (X - self.mean_) / self.std_

        self.model = IsolationForest(
            n_estimators=600,
            contamination=self.contamination,
            random_state=self.random_state,
        )
        self.model.fit(Xn)

        self._risk_ema = None
        self._momentum = 0.0
        self._outlier_streak = 0
        self._highrisk_streak = 0

    # -------------------------
    # Evaluation
    # -------------------------
    def evaluate(self, feat: Dict[str, float], policy_boost: float = 0.0) -> RiskResult:
        if self.model is None or self.mean_ is None or self.std_ is None:
            return RiskResult(0.0, "LOW", "ALLOW", 0.0)

        x = features_to_vector(feat).reshape(1, -1)
        xn = (x - self.mean_) / self.std_

        normality = float(self.model.decision_function(xn)[0])  # higher = more normal
        pred = int(self.model.predict(xn)[0])                   # +1 inlier, -1 outlier

        # base risk
        risk_raw = float(self._score_to_risk(normality))

        # outlier boost
        if pred == -1:
            risk_raw += self.outlier_boost

        # external boost (optional)
        if policy_boost > 0:
            risk_raw += float(policy_boost)

        # ---------------------------------------
        # Coupling-break penalty (NEW)
        # ---------------------------------------
        # These rules detect "impossible combinations" that often occur in bots/macros.
        # They DO NOT force BLOCK, only raise risk.
        kr = float(feat.get("key_rate", 0.0))
        iki_m = float(feat.get("iki_mean", 0.0))
        iki_s = float(feat.get("iki_std", 0.0))
        hm = float(feat.get("hold_mean", 0.0))
        hs = float(feat.get("hold_std", 0.0))
        ms_m = float(feat.get("mouse_speed_mean", 0.0))
        ms_s = float(feat.get("mouse_speed_std", 0.0))
        cr = float(feat.get("click_rate", 0.0))

        # High key_rate but slow inter-key timing is inconsistent
        if kr > 25 and iki_m > 0.12:
            risk_raw += 12.0

        # Extremely high variance is suspicious (macro jitter / synthetic)
        if iki_s > 2.5 or hs > 2.5:
            risk_raw += 10.0

        # Teleport mouse: huge std relative to mean
        if ms_m > 2000 and ms_s > (ms_m * 1.8):
            risk_raw += 12.0

        # High click with very low mouse mean can be macro clicking
        if cr > 12 and ms_m < 800:
            risk_raw += 10.0

        # clamp
        risk_raw = float(max(0.0, min(100.0, risk_raw)))

        # ---------------------------------------
        # Persistence counters
        # ---------------------------------------
        if pred == -1:
            self._outlier_streak += 1
        else:
            self._outlier_streak = max(0, self._outlier_streak - 1)

        if risk_raw >= self.high_risk_gate:
            self._highrisk_streak += 1
        else:
            self._highrisk_streak = max(0, self._highrisk_streak - 1)

        # ---------------------------------------
        # Momentum (attack memory)
        # ---------------------------------------
        suspicious = (pred == -1) or (risk_raw >= self.high_risk_gate)
        if suspicious:
            self._momentum = min(1.0, self._momentum * 0.98 + self.momentum_alpha)
        else:
            self._momentum = max(0.0, self._momentum * self.momentum_decay)

        risk_raw += 25.0 * self._momentum
        risk_raw = float(max(0.0, min(100.0, risk_raw)))

        # ---------------------------------------
        # EMA smoothing (UI stability)
        # ---------------------------------------
        if self._risk_ema is None:
            self._risk_ema = risk_raw
        else:
            a = self.ema_alpha
            self._risk_ema = (a * risk_raw) + ((1.0 - a) * self._risk_ema)

        risk_smooth = float(self._risk_ema)

        # Bypass smoothing for strong outliers so attacks don't get hidden
        if pred == -1 and risk_raw >= self.bypass_smoothing_gate:
            risk_final = risk_raw
        else:
            risk_final = risk_smooth

        # ---------------------------------------
        # Decision logic
        # ---------------------------------------
        forced_block = (
            (self._outlier_streak >= self.outlier_strikes_block) or
            (self._highrisk_streak >= self.high_risk_strikes_block)
        )

        if forced_block or (risk_final >= self.high_threshold):
            return RiskResult(float(risk_final), "HIGH", "BLOCK", normality)

        if risk_final >= self.low_threshold:
            return RiskResult(float(risk_final), "MEDIUM", "STEP_UP", normality)

        return RiskResult(float(risk_final), "LOW", "ALLOW", normality)

    # -------------------------
    # Risk mapping
    # -------------------------
    @staticmethod
    def _sigmoid(z: float) -> float:
        return 1.0 / (1.0 + np.exp(-z))

    def _score_to_risk(self, normality: float) -> float:
        z = (-normality) * self.score_scale
        r01 = float(self._sigmoid(z))
        return 100.0 * r01