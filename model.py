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
    risk_score: float     # 0..100
    level: str            # LOW / MEDIUM / HIGH
    action: str           # ALLOW / STEP_UP / BLOCK
    anomaly_score: float  # model score (decision_function; higher=more normal)


class DigitalTwinModel:
    """
    Cognitive Digital Twin model using:
    - Feature normalization learned from enrollment samples (mean/std)
    - Isolation Forest anomaly detector
    - Smooth risk mapping so decisions are stable
    """

    def __init__(
        self,
        contamination: float = 0.10,
        low_threshold: float = 35.0,
        high_threshold: float = 70.0,
        random_state: int = 42
    ):
        self.model: Optional[IsolationForest] = None
        self.mean_: Optional[np.ndarray] = None
        self.std_: Optional[np.ndarray] = None

        self.contamination = float(contamination)
        self.low_threshold = float(low_threshold)
        self.high_threshold = float(high_threshold)
        self.random_state = int(random_state)

    # -------------------------
    # Training
    # -------------------------
    def train(self, samples: List[Dict[str, float]]) -> None:
        if not samples:
            self.model = None
            self.mean_ = None
            self.std_ = None
            return

        X = np.vstack([features_to_vector(s) for s in samples])

        # Learn normalization stats from enrollment
        self.mean_ = X.mean(axis=0)
        self.std_ = X.std(axis=0)

        # Prevent divide-by-zero
        self.std_ = np.where(self.std_ < 1e-6, 1.0, self.std_)

        Xn = (X - self.mean_) / self.std_

        self.model = IsolationForest(
            n_estimators=300,
            contamination=self.contamination,  # sensitivity
            random_state=self.random_state,
        )
        self.model.fit(Xn)

    # -------------------------
    # Evaluation
    # -------------------------
    def evaluate(self, feat: Dict[str, float]) -> RiskResult:
        if self.model is None or self.mean_ is None or self.std_ is None:
            return RiskResult(0.0, "LOW", "ALLOW", 0.0)

        x = features_to_vector(feat).reshape(1, -1)
        xn = (x - self.mean_) / self.std_

        # Higher = more normal
        normality = float(self.model.decision_function(xn)[0])

        # Convert to risk (0..100)
        risk = float(self._score_to_risk(normality))

        if risk < self.low_threshold:
            level, action = "LOW", "ALLOW"
        elif risk < self.high_threshold:
            level, action = "MEDIUM", "STEP_UP"
        else:
            level, action = "HIGH", "BLOCK"

        return RiskResult(risk, level, action, normality)

    # -------------------------
    # Risk mapping
    # -------------------------
    @staticmethod
    def _sigmoid(z: float) -> float:
        return 1.0 / (1.0 + np.exp(-z))

    def _score_to_risk(self, normality: float) -> float:
        """
        decision_function is typically in a small range (~ -0.2..+0.2 but depends).
        We map normality -> risk using a sigmoid around 0.

        Lower normality => higher risk.
        """

        scale = 10.0
        z = (-normality) * scale

        r01 = self._sigmoid(z)  # 0..1
        return max(0.0, min(100.0, 100.0 * r01))
