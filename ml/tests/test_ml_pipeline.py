import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
import yaml

ML_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = ML_DIR.parent
for p in [str(PROJECT_ROOT), str(ML_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

ARTIFACTS_DIR = ML_DIR / "artifacts"


def test_column_mapping_excludes_leaked_columns():
    """Verify that all contemporaneous measurements are strictly excluded from features."""
    with open(ML_DIR / "column_mapping.yaml", "r", encoding="utf-8") as f:
        col_config = yaml.safe_load(f)

    excluded = col_config.get("excluded_columns", [])
    expected_leaked = [
        "Traffic Volume",
        "Average Speed",
        "Congestion Level",
        "Road Capacity Utilization",
        "Incident Reports",
    ]
    for leak in expected_leaked:
        assert leak in excluded, f"Leaked column '{leak}' must be strictly excluded."


def test_data_validation_and_clean_pipeline():
    """Verify data preparation cleans duplicates and formats features."""
    from ml.prepare import prepare_dataset

    df, summary = prepare_dataset(save_cleaned=False)

    assert len(df) > 0
    assert summary["final_rows"] > 0
    assert "target" in df.columns
    assert (df["target"] >= 1.0).all(), "All target values must be >= 1.0"
    assert (df["target"] <= 2.0).all(), "All target values must be clipped at max threshold"
    assert not df["area"].isna().any(), "No missing areas allowed"
    assert not df["weather"].isna().any(), "No missing weather conditions allowed"


def test_no_temporal_overlap_in_splits():
    """Verify time-based split has zero temporal overlap between train and validation."""
    from ml.prepare import prepare_dataset

    clean_df, _ = prepare_dataset(save_cleaned=False)
    unique_dates = sorted(clean_df["date"].unique())
    val_cutoff_idx = int(len(unique_dates) * 0.85)
    val_cutoff_date = unique_dates[val_cutoff_idx]

    train_dates = clean_df[clean_df["date"] < val_cutoff_date]["date"]
    val_dates = clean_df[clean_df["date"] >= val_cutoff_date]["date"]

    assert train_dates.max() < val_dates.min(), "Train dates must strictly precede validation dates."
    train_set = set(train_dates)
    val_set = set(val_dates)
    assert train_set.isdisjoint(val_set), "No date overlap permitted between train and validation sets."


def test_predictions_always_greater_or_equal_to_one():
    """Verify that model predictions are strictly >= 1.0."""
    from ml.predictor import CongestionPredictorWrapper
    from unittest.mock import MagicMock

    # Test wrapper clipping
    mock_pipeline = MagicMock()
    # Mock pipeline returning values below 1.0 and above 1.0
    mock_pipeline.predict.return_value = np.array([0.85, 0.99, 1.0, 1.25, 1.50, 0.4])
    wrapper = CongestionPredictorWrapper(mock_pipeline)

    sample_X = pd.DataFrame([{"area": "Indiranagar", "weather": "Clear", "weekday": 1, "is_weekend": 0, "month": 3, "is_holiday": 0}] * 6)
    preds = wrapper.predict(sample_X)

    assert (preds >= 1.0).all(), f"All predictions must be >= 1.0, but got {preds}"
    assert preds[0] == 1.0
    assert preds[1] == 1.0
    assert preds[3] == 1.25


def test_zones_configuration():
    """Verify ml/zones.json covers areas from dataset and specifies approximate: true."""
    zones_path = ML_DIR / "zones.json"
    assert zones_path.exists(), "ml/zones.json must exist"

    with open(zones_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "zones" in data
    zones = data["zones"]
    assert len(zones) >= 8

    for z in zones:
        assert "name" in z
        assert "lat" in z and -90 <= z["lat"] <= 90
        assert "lng" in z and -180 <= z["lng"] <= 180
        assert "radius_km" in z and z["radius_km"] > 0
        assert z.get("approximate") is True, f"Zone {z['name']} must be marked approximate: true"
