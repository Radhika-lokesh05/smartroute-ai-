"""
Traffic congestion ML prediction service and spatial zone mapper.
Performs length-weighted route sampling, zone haversine lookups, and factor predictions.
Fails safely with factor 1.0 and model_available=false if model is missing.
"""
import json
import logging
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
try:
    import joblib
except ImportError:
    joblib = None

try:
    import numpy as np
except ImportError:
    np = None

try:
    import pandas as pd
except ImportError:
    pd = None

from app.core.config import settings
from app.services.realtime import haversine_distance_m

logger = logging.getLogger("smartroute.ml.traffic_model")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
WORKSPACE_DIR = BASE_DIR.parent
for p in [str(WORKSPACE_DIR), str(WORKSPACE_DIR / "ml")]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from ml.predictor import CongestionPredictorWrapper
except ImportError:
    try:
        from predictor import CongestionPredictorWrapper
    except ImportError:
        CongestionPredictorWrapper = None


def is_karnataka_holiday(d) -> int:
    """Check if date is a public holiday in Karnataka."""
    try:
        import holidays
        in_holidays = holidays.country_holidays("IN", subdiv="KA")
        return 1 if d in in_holidays else 0
    except ImportError:
        fixed = {(1, 26), (8, 15), (10, 2), (11, 1), (12, 25), (1, 1)}
        return 1 if (d.month, d.day) in fixed else 0


class TrafficModelService:
    """Manages pre-trained congestion model and spatial zone resolution."""

    def __init__(self) -> None:
        self.model: Optional[Any] = None
        self.model_available: bool = False
        self.model_version: str = "v1.0.0"
        self.data_source: str = "kaggle-bangalore-city-traffic"
        self.data_granularity: str = "daily"
        self.zones: List[Dict[str, Any]] = []
        self._load_zones()
        self._load_model()

    def _resolve_path(self, relative_path: str) -> Path:
        """Resolve path relative to backend parent directory or workspace root."""
        p = Path(relative_path)
        if p.is_absolute() and p.exists():
            return p
        # Check backend parent (workspace root)
        candidate1 = BASE_DIR.parent / relative_path
        if candidate1.exists():
            return candidate1
        candidate2 = BASE_DIR / relative_path
        if candidate2.exists():
            return candidate2
        return candidate1

    def _load_zones(self) -> None:
        """Load geographical zone centroids and radii from zones.json."""
        zones_file = self._resolve_path(settings.TRAFFIC_ZONES_PATH)
        if zones_file.exists():
            try:
                data = json.loads(zones_file.read_text(encoding="utf-8"))
                self.zones = data.get("zones", [])
                logger.info("Loaded %d traffic zones from %s", len(self.zones), zones_file)
            except Exception as exc:
                logger.warning("Could not parse zones file %s: %s", zones_file, exc)
        else:
            logger.warning("Traffic zones file not found at %s", zones_file)

    def _load_model(self) -> None:
        """Load model.joblib once at startup. Fails safely if missing or joblib not installed."""
        if joblib is None:
            logger.warning("joblib is not installed. Operating with factor 1.0.")
            self.model_available = False
            self.model = None
            return

        model_file = self._resolve_path(settings.TRAFFIC_MODEL_PATH)
        if model_file.exists():
            try:
                self.model = joblib.load(model_file)
                self.model_available = True
                if hasattr(self.model, "model_version"):
                    self.model_version = self.model.model_version
                logger.info("Loaded traffic ML model from %s", model_file)
            except Exception as exc:
                logger.warning("Failed to load traffic model from %s: %s. Operating with factor 1.0.", model_file, exc)
                self.model_available = False
                self.model = None
        else:
            logger.warning("Traffic model artifact not found at %s. Operating with factor 1.0.", model_file)
            self.model_available = False
            self.model = None

    def get_zone_for_point(self, lat: float, lng: float) -> Tuple[str, float]:
        """
        Identify closest known zone by haversine distance.
        If distance exceeds zone radius + margin, returns ('unknown', min_distance_km).
        Never extrapolates to unfamiliar geographic areas.
        """
        if not self.zones:
            return "unknown", float("inf")

        best_zone = "unknown"
        min_dist_m = float("inf")
        matched_radius_m = 0.0

        for z in self.zones:
            dist_m = haversine_distance_m(lat, lng, z["lat"], z["lng"])
            if dist_m < min_dist_m:
                min_dist_m = dist_m
                best_zone = z["name"]
                matched_radius_m = (z.get("radius_km", 3.0) + settings.ZONE_RADIUS_MARGIN_KM) * 1000.0

        if min_dist_m <= matched_radius_m:
            return best_zone, round(min_dist_m / 1000.0, 2)
        return "unknown", round(min_dist_m / 1000.0, 2)

    def predict_factor(
        self,
        zone: str,
        when: datetime,
        weather: str = "Clear",
    ) -> float:
        """
        Predict congestion factor (>= 1.0) for a given zone, departure datetime, and weather.
        Returns 1.0 for unknown zones or when model or pandas is unavailable.
        """
        if zone == "unknown" or not self.model_available or self.model is None or pd is None:
            return 1.0

        weekday = when.weekday()
        is_weekend = 1 if weekday >= 5 else 0
        month = when.month
        is_holiday = is_karnataka_holiday(when.date())

        features_df = pd.DataFrame([
            {
                "area": zone,
                "weather": weather,
                "weekday": weekday,
                "is_weekend": is_weekend,
                "month": month,
                "is_holiday": is_holiday,
            }
        ])

        try:
            factor = float(self.model.predict(features_df)[0])
            return max(1.0, round(factor, 3))
        except Exception as exc:
            logger.warning("Prediction error for zone %s: %s", zone, exc)
            return 1.0

    def calculate_route_traffic(
        self,
        coordinates: List[List[float]],
        when: datetime,
        weather: str = "Clear",
        max_samples: int = 20,
    ) -> Tuple[float, float]:
        """
        Sample at most max_samples along route LineString and calculate length-weighted
        traffic congestion factor and coverage.
        Returns: (traffic_factor, traffic_coverage).
        """
        if not coordinates or len(coordinates) < 2:
            return 1.0, 0.0

        # Calculate distances of all segments in the linestring
        segments: List[Tuple[float, float, float, float, float]] = [] # (p1_lat, p1_lng, p2_lat, p2_lng, length_m)
        total_len_m = 0.0

        for i in range(len(coordinates) - 1):
            p1_lng, p1_lat = coordinates[i][0], coordinates[i][1]
            p2_lng, p2_lat = coordinates[i + 1][0], coordinates[i + 1][1]
            seg_len = haversine_distance_m(p1_lat, p1_lng, p2_lat, p2_lng)
            if seg_len > 0:
                segments.append((p1_lat, p1_lng, p2_lat, p2_lng, seg_len))
                total_len_m += seg_len

        if total_len_m <= 0:
            return 1.0, 0.0

        # Subsample segments to at most max_samples evenly spaced
        if len(segments) > max_samples:
            step = len(segments) / float(max_samples)
            sampled_segments = [segments[int(i * step)] for i in range(max_samples)]
        else:
            sampled_segments = segments

        sampled_total_len = sum(s[4] for s in sampled_segments)
        if sampled_total_len <= 0:
            return 1.0, 0.0

        weighted_factor_sum = 0.0
        covered_len_m = 0.0

        for p1_lat, p1_lng, p2_lat, p2_lng, seg_len in sampled_segments:
            mid_lat = (p1_lat + p2_lat) / 2.0
            mid_lng = (p1_lng + p2_lng) / 2.0

            zone_name, _ = self.get_zone_for_point(mid_lat, mid_lng)
            if zone_name != "unknown":
                factor = self.predict_factor(zone_name, when, weather)
                covered_len_m += seg_len
            else:
                factor = 1.0

            weighted_factor_sum += factor * seg_len

        length_weighted_factor = weighted_factor_sum / sampled_total_len
        coverage = covered_len_m / sampled_total_len

        return max(1.0, round(length_weighted_factor, 3)), min(1.0, max(0.0, round(coverage, 2)))


traffic_model_service = TrafficModelService()
