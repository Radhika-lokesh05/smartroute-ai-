"""
Model training pipeline for Bengaluru traffic congestion prediction.
Enforces chronological time-based split, compares against a naive baseline,
trains a LightGBM regressor, evaluates MAE/RMSE/R2, and saves model artifacts and diagnostic plots.
"""
import json
import logging
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import Pipeline
import lightgbm as lgb
import yaml

ML_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = ML_DIR.parent
for p in [str(PROJECT_ROOT), str(ML_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from ml.prepare import prepare_dataset
    from ml.predictor import CongestionPredictorWrapper
except ImportError:
    from prepare import prepare_dataset
    from predictor import CongestionPredictorWrapper

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("smartroute.ml.train")

ARTIFACTS_DIR = ML_DIR / "artifacts"


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    mae = float(mean_absolute_error(y_true, y_pred))
    mse = float(mean_squared_error(y_true, y_pred))
    rmse = float(math.sqrt(mse))
    r2 = float(r2_score(y_true, y_pred))
    return {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "r2": round(r2, 4),
    }


def train_model():
    """Train LightGBM regressor on time-based split and compare with naive baseline."""
    with open(ML_DIR / "config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # 1. Prepare data
    clean_df, data_summary = prepare_dataset(save_cleaned=True)

    # 2. Time-Based Split (Last 15% of dates for validation, never random)
    unique_dates = sorted(clean_df["date"].unique())
    val_ratio = float(config.get("validation_split_ratio", 0.15))
    val_cutoff_idx = int(len(unique_dates) * (1.0 - val_ratio))
    val_cutoff_date = unique_dates[val_cutoff_idx]

    train_df = clean_df[clean_df["date"] < val_cutoff_date].copy()
    val_df = clean_df[clean_df["date"] >= val_cutoff_date].copy()

    logger.info("Total unique dates: %d", len(unique_dates))
    logger.info("Validation cutoff date: %s", val_cutoff_date)
    logger.info("Train rows: %d (Dates: %s to %s)", len(train_df), train_df["date"].min(), train_df["date"].max())
    logger.info("Val rows: %d (Dates: %s to %s)", len(val_df), val_df["date"].min(), val_df["date"].max())

    feature_cols = ["area", "weather", "weekday", "is_weekend", "month", "is_holiday"]
    target_col = "target"

    X_train = train_df[feature_cols]
    y_train = train_df[target_col].values
    X_val = val_df[feature_cols]
    y_val = val_df[target_col].values

    # 3. Naive Baseline (Mean target by area and weekday on training set)
    baseline_lookup = train_df.groupby(["area", "weekday"])["target"].mean().to_dict()
    area_lookup = train_df.groupby("area")["target"].mean().to_dict()
    global_mean = float(train_df["target"].mean())

    val_baseline_preds = []
    for _, row in X_val.iterrows():
        key = (row["area"], row["weekday"])
        if key in baseline_lookup:
            pred = baseline_lookup[key]
        elif row["area"] in area_lookup:
            pred = area_lookup[row["area"]]
        else:
            pred = global_mean
        val_baseline_preds.append(max(1.0, pred))
    val_baseline_preds = np.array(val_baseline_preds)
    baseline_metrics = compute_metrics(y_val, val_baseline_preds)
    logger.info("Baseline Metrics on Validation Set: %s", baseline_metrics)

    # 4. LightGBM Pipeline
    cat_features = ["area", "weather"]
    num_features = ["weekday", "is_weekend", "month", "is_holiday"]

    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), cat_features),
            ("num", "passthrough", num_features),
        ]
    )

    lgb_params = config.get("lightgbm_params", {})
    regressor = lgb.LGBMRegressor(**lgb_params)

    pipeline = Pipeline(steps=[("preprocessor", preprocessor), ("regressor", regressor)])

    logger.info("Fitting LightGBM Regressor pipeline...")
    pipeline.fit(X_train, y_train)

    # Predictions
    raw_val_preds = pipeline.predict(X_val)
    val_preds = np.clip(raw_val_preds, 1.0, 3.0)
    model_metrics = compute_metrics(y_val, val_preds)
    logger.info("LightGBM Model Metrics on Validation Set: %s", model_metrics)

    # Comparison check
    model_beats_baseline = (model_metrics["mae"] <= baseline_metrics["mae"]) and (model_metrics["rmse"] <= baseline_metrics["rmse"])
    logger.info("Does model beat naive baseline? %s", model_beats_baseline)

    # 5. Feature Importance Extraction
    fitted_preprocessor = pipeline.named_steps["preprocessor"]
    fitted_model = pipeline.named_steps["regressor"]
    ohe_feature_names = fitted_preprocessor.named_transformers_["cat"].get_feature_names_out(cat_features).tolist()
    all_feature_names = ohe_feature_names + num_features
    importances = fitted_model.feature_importances_.tolist()
    feature_importance_dict = dict(sorted(zip(all_feature_names, importances), key=lambda x: x[1], reverse=True))

    # 6. Save Model Artifact
    wrapped_model = CongestionPredictorWrapper(pipeline, model_version=config.get("model_version", "v1.0.0"))
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    model_out_path = ARTIFACTS_DIR / "model.joblib"
    joblib.dump(wrapped_model, model_out_path)
    logger.info("Saved trained model to %s", model_out_path)

    # 7. Generate Diagnostic Plots (Matplotlib)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        # Plot 1: Actual vs Predicted
        plt.figure(figsize=(8, 6))
        plt.scatter(y_val, val_preds, alpha=0.3, color="#06B6D4", edgecolors="none")
        plt.plot([1.0, 1.6], [1.0, 1.6], color="#F43F5E", linestyle="--", label="Ideal Fit (y = x)")
        plt.xlabel("Actual Travel Time Index (Validation)")
        plt.ylabel("Predicted Congestion Factor")
        plt.title(f"Actual vs Predicted Congestion Factor (MAE: {model_metrics['mae']})")
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.tight_layout()
        plt.savefig(ARTIFACTS_DIR / "actual_vs_predicted.png", dpi=150)
        plt.close()

        # Plot 2: Feature Importance (Top 15)
        top_items = list(feature_importance_dict.items())[:15]
        top_names, top_vals = zip(*top_items)
        plt.figure(figsize=(10, 6))
        plt.barh(range(len(top_names)), top_vals, color="#0EA5E9")
        plt.yticks(range(len(top_names)), top_names)
        plt.gca().invert_yaxis()
        plt.xlabel("Importance (Split Count)")
        plt.title("Top Feature Importances (LightGBM)")
        plt.tight_layout()
        plt.savefig(ARTIFACTS_DIR / "feature_importance.png", dpi=150)
        plt.close()

        # Plot 3: Error by Area
        val_df["pred"] = val_preds
        val_df["abs_error"] = np.abs(val_df["target"] - val_df["pred"])
        area_errors = val_df.groupby("area")["abs_error"].mean().sort_values()

        plt.figure(figsize=(9, 5))
        area_errors.plot(kind="bar", color="#F59E0B")
        plt.ylabel("Mean Absolute Error (MAE)")
        plt.xlabel("Bengaluru Area")
        plt.title("Validation Error by Area")
        plt.xticks(rotation=30, ha="right")
        plt.tight_layout()
        plt.savefig(ARTIFACTS_DIR / "error_by_area.png", dpi=150)
        plt.close()
        logger.info("Saved 3 diagnostic plots to %s", ARTIFACTS_DIR)
    except Exception as exc:
        logger.warning("Could not generate plots: %s", exc)

    # 8. Save Metrics JSON
    metrics_report = {
        "data_source": config.get("data_source", "kaggle-bangalore-city-traffic"),
        "file_name": "Banglore_traffic_Dataset.csv",
        "model_version": config.get("model_version", "v1.0.0"),
        "training_date": datetime.now(timezone.utc).isoformat(),
        "granularity": config.get("data_granularity", "daily"),
        "train_rows": len(train_df),
        "val_rows": len(val_df),
        "train_date_range": [str(train_df["date"].min()), str(train_df["date"].max())],
        "val_date_range": [str(val_df["date"].min()), str(val_df["date"].max())],
        "areas_covered": sorted(clean_df["area"].unique().tolist()),
        "metrics": {
            "lightgbm": model_metrics,
            "baseline": baseline_metrics,
            "model_beats_baseline": model_beats_baseline,
            "mae_improvement_pct": round(((baseline_metrics["mae"] - model_metrics["mae"]) / baseline_metrics["mae"]) * 100, 2),
        },
        "feature_importance_top10": dict(list(feature_importance_dict.items())[:10]),
    }

    metrics_out_path = ARTIFACTS_DIR / "metrics.json"
    with open(metrics_out_path, "w", encoding="utf-8") as f:
        json.dump(metrics_report, f, indent=2)
    logger.info("Saved metrics report to %s", metrics_out_path)

    return metrics_report


if __name__ == "__main__":
    train_model()
