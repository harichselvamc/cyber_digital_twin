"""
Multi-Model Fusion Module

Combines multiple anomaly detection models for improved accuracy and robustness:
- Isolation Forest (tree-based anomaly detection)
- One-Class SVM (boundary-based novelty detection)
- Autoencoder (deep learning reconstruction error)

Final decision = weighted ensemble output.
"""

from __future__ import annotations

import numpy as np
from typing import Dict, List, Optional, Tuple
from sklearn.ensemble import IsolationForest
from sklearn.svm import OneClassSVM
from sklearn.preprocessing import StandardScaler


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


class SimpleAutoencoder:
    """
    Lightweight autoencoder using numpy (no torch/tf dependency).
    Uses a simple 3-layer network: input -> hidden -> output.
    Anomaly = high reconstruction error.
    """

    def __init__(self, input_dim: int = 8, hidden_dim: int = 4, learning_rate: float = 0.01, epochs: int = 200):
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.lr = learning_rate
        self.epochs = epochs

        # Xavier initialization
        self.W1 = np.random.randn(input_dim, hidden_dim) * np.sqrt(2.0 / input_dim)
        self.b1 = np.zeros(hidden_dim)
        self.W2 = np.random.randn(hidden_dim, input_dim) * np.sqrt(2.0 / hidden_dim)
        self.b2 = np.zeros(input_dim)

        self._fitted = False
        self._threshold = 0.0

    @staticmethod
    def _relu(x):
        return np.maximum(0, x)

    @staticmethod
    def _relu_grad(x):
        return (x > 0).astype(float)

    def _forward(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        hidden = self._relu(X @ self.W1 + self.b1)
        output = hidden @ self.W2 + self.b2
        return hidden, output

    def fit(self, X: np.ndarray) -> None:
        n = X.shape[0]
        for _ in range(self.epochs):
            hidden, output = self._forward(X)
            error = output - X

            # Backpropagation
            dW2 = hidden.T @ error / n
            db2 = error.mean(axis=0)

            dhidden = error @ self.W2.T * self._relu_grad(X @ self.W1 + self.b1)
            dW1 = X.T @ dhidden / n
            db1 = dhidden.mean(axis=0)

            self.W1 -= self.lr * dW1
            self.b1 -= self.lr * db1
            self.W2 -= self.lr * dW2
            self.b2 -= self.lr * db2

        # Set threshold as 95th percentile of training reconstruction error
        _, recon = self._forward(X)
        errors = np.mean((X - recon) ** 2, axis=1)
        self._threshold = float(np.percentile(errors, 95))
        self._fitted = True

    def reconstruction_error(self, X: np.ndarray) -> np.ndarray:
        _, recon = self._forward(X)
        return np.mean((X - recon) ** 2, axis=1)

    def anomaly_score(self, X: np.ndarray) -> float:
        """Returns normalized anomaly score (0=normal, 1=highly anomalous)."""
        if not self._fitted:
            return 0.0
        error = float(self.reconstruction_error(X)[0])
        if self._threshold <= 0:
            return 0.0
        score = error / (self._threshold * 2)
        return float(min(1.0, max(0.0, score)))


class FusionModel:
    """
    Multi-model fusion for anomaly detection.
    Combines: Isolation Forest + One-Class SVM + Autoencoder.
    """

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        contamination: float = 0.03,
    ):
        self.weights = weights or {
            "isolation_forest": 0.45,
            "one_class_svm": 0.30,
            "autoencoder": 0.25,
        }
        self.contamination = contamination

        self.iforest: Optional[IsolationForest] = None
        self.ocsvm: Optional[OneClassSVM] = None
        self.autoencoder: Optional[SimpleAutoencoder] = None
        self.scaler: Optional[StandardScaler] = None

        self._fitted = False

    def train(self, samples: List[Dict[str, float]]) -> None:
        if not samples or len(samples) < 5:
            self._fitted = False
            return

        X = np.vstack([features_to_vector(s) for s in samples])

        self.scaler = StandardScaler()
        Xn = self.scaler.fit_transform(X)

        # 1. Isolation Forest
        self.iforest = IsolationForest(
            n_estimators=600,
            contamination=self.contamination,
            random_state=42,
        )
        self.iforest.fit(Xn)

        # 2. One-Class SVM
        self.ocsvm = OneClassSVM(
            kernel='rbf',
            gamma='scale',
            nu=self.contamination,
        )
        self.ocsvm.fit(Xn)

        # 3. Autoencoder
        self.autoencoder = SimpleAutoencoder(
            input_dim=Xn.shape[1],
            hidden_dim=max(3, Xn.shape[1] // 2),
            learning_rate=0.005,
            epochs=300,
        )
        self.autoencoder.fit(Xn)

        self._fitted = True

    def evaluate(self, feat: Dict[str, float]) -> Dict:
        """
        Returns fused anomaly assessment.
        """
        if not self._fitted:
            return {
                "fused_score": 0.0,
                "model_scores": {},
                "is_anomaly": False,
            }

        x = features_to_vector(feat).reshape(1, -1)
        xn = self.scaler.transform(x)

        scores = {}

        # Isolation Forest: decision_function (negative = anomalous)
        if_score = float(self.iforest.decision_function(xn)[0])
        if_pred = int(self.iforest.predict(xn)[0])
        # Normalize: map to 0-1 where 1 = anomalous
        if_anomaly = max(0.0, min(1.0, 0.5 - if_score * 2.0))
        scores["isolation_forest"] = round(if_anomaly, 4)

        # One-Class SVM: decision_function (negative = anomalous)
        svm_score = float(self.ocsvm.decision_function(xn)[0])
        svm_pred = int(self.ocsvm.predict(xn)[0])
        svm_anomaly = max(0.0, min(1.0, 0.5 - svm_score * 0.5))
        scores["one_class_svm"] = round(svm_anomaly, 4)

        # Autoencoder: reconstruction error
        ae_anomaly = self.autoencoder.anomaly_score(xn)
        scores["autoencoder"] = round(ae_anomaly, 4)

        # Weighted fusion
        fused = sum(
            scores[model] * self.weights[model]
            for model in self.weights
        )
        fused = round(min(1.0, max(0.0, fused)), 4)

        # Convert to risk-like score (0-100)
        risk_equivalent = fused * 100.0

        return {
            "fused_score": round(risk_equivalent, 2),
            "model_scores": scores,
            "is_anomaly": fused > 0.5,
            "individual_predictions": {
                "isolation_forest": if_pred == -1,
                "one_class_svm": svm_pred == -1,
                "autoencoder": ae_anomaly > 0.5,
            },
        }
