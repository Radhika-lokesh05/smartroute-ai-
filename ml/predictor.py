"""
Congestion predictor wrapper for traffic model.
Ensures predictions are strictly clipped >= 1.0 and safe for serialization.
"""
from typing import Any
import numpy as np
import pandas as pd


class CongestionPredictorWrapper:
    """Wrapper pipeline guaranteeing all predictions are strictly clipped >= 1.0."""

    def __init__(self, pipeline: Any, model_version: str = "v1.0.0") -> None:
        self.pipeline = pipeline
        self.model_version = model_version

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        raw_preds = self.pipeline.predict(X)
        return np.clip(raw_preds, 1.0, 3.0)
