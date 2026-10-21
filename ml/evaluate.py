"""
Model evaluation script. Reloads trained model.joblib and prints metrics.json summary.
"""
import json
import logging
import sys
from pathlib import Path
import joblib
import pandas as pd

ML_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = ML_DIR.parent
for p in [str(PROJECT_ROOT), str(ML_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from ml.predictor import CongestionPredictorWrapper
except ImportError:
    from predictor import CongestionPredictorWrapper

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("smartroute.ml.evaluate")

ARTIFACTS_DIR = ML_DIR / "artifacts"


def evaluate_model():
    """Reload saved model and display performance metrics."""
    metrics_path = ARTIFACTS_DIR / "metrics.json"
    model_path = ARTIFACTS_DIR / "model.joblib"

    if not model_path.exists():
        logger.error("model.joblib not found at %s. Please run train.py first.", model_path)
        return

    # Verify model loading
    model = joblib.load(model_path)
    logger.info("Successfully reloaded model from %s", model_path)

    # Test sample prediction
    sample_df = pd.DataFrame([
        {"area": "Indiranagar", "weather": "Clear", "weekday": 0, "is_weekend": 0, "month": 5, "is_holiday": 0},
        {"area": "Koramangala", "weather": "Rain", "weekday": 4, "is_weekend": 0, "month": 8, "is_holiday": 0},
        {"area": "Whitefield", "weather": "Fog", "weekday": 6, "is_weekend": 1, "month": 1, "is_holiday": 0},
    ])
    preds = model.predict(sample_df)
    logger.info("Sample predictions (all >= 1.0): %s", [round(float(p), 4) for p in preds])

    if metrics_path.exists():
        with open(metrics_path, "r", encoding="utf-8") as f:
            metrics = json.load(f)

        print("\n" + "=" * 60)
        print(f"TRAFFIC MODEL EVALUATION SUMMARY ({metrics.get('model_version')})")
        print("=" * 60)
        print(f"Data Source       : {metrics.get('data_source')}")
        print(f"Dataset File      : {metrics.get('file_name')}")
        print(f"Granularity       : {metrics.get('granularity')}")
        print(f"Train Date Range  : {metrics.get('train_date_range')}")
        print(f"Val Date Range    : {metrics.get('val_date_range')}")
        print(f"Train / Val Rows  : {metrics.get('train_rows')} / {metrics.get('val_rows')}")
        print("-" * 60)
        print(f"LightGBM Model    : MAE={metrics['metrics']['lightgbm']['mae']:.4f}, RMSE={metrics['metrics']['lightgbm']['rmse']:.4f}, R2={metrics['metrics']['lightgbm']['r2']:.4f}")
        print(f"Naive Baseline    : MAE={metrics['metrics']['baseline']['mae']:.4f}, RMSE={metrics['metrics']['baseline']['rmse']:.4f}, R2={metrics['metrics']['baseline']['r2']:.4f}")
        print(f"Model Beats Base? : {'YES (MAE improved by ' + str(metrics['metrics']['mae_improvement_pct']) + '%)' if metrics['metrics']['model_beats_baseline'] else 'NO'}")
        print("=" * 60 + "\n")


if __name__ == "__main__":
    evaluate_model()
