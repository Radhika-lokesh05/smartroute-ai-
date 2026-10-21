"""
Data preparation and validation pipeline for Bengaluru traffic dataset.
Cleans, deduplicates, parses dates, derives prediction-time features, and clips the target.
"""
import logging
from pathlib import Path
from typing import Dict, Tuple, Optional
import pandas as pd
import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("smartroute.ml.prepare")

ML_DIR = Path(__file__).resolve().parent
DATA_DIR = ML_DIR / "data"
ARTIFACTS_DIR = ML_DIR / "artifacts"


def load_yaml(path: Path) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_holiday_checker():
    """Return holiday lookup function using the holidays package (Karnataka, India) with fallback."""
    try:
        import holidays
        in_holidays = holidays.country_holidays("IN", subdiv="KA")
        return lambda d: 1 if d in in_holidays else 0
    except ImportError:
        logger.warning("Package 'holidays' not installed. Falling back to default holiday calendar.")
        # Common major Indian national holidays
        fixed_holidays = {
            (1, 26),  # Republic Day
            (8, 15),  # Independence Day
            (10, 2),  # Gandhi Jayanti
            (11, 1),  # Kannada Rajyotsava
            (12, 25), # Christmas
            (1, 1),   # New Year
        }
        return lambda d: 1 if (d.month, d.day) in fixed_holidays else 0


def prepare_dataset(
    data_path: Optional[Path] = None,
    save_cleaned: bool = True,
) -> Tuple[pd.DataFrame, Dict]:
    """
    Load raw traffic dataset, validate, deduplicate, engineer prediction-time features,
    and drop leaked columns.
    Returns: (cleaned_df, summary_stats).
    """
    col_config = load_yaml(ML_DIR / "column_mapping.yaml")
    model_config = load_yaml(ML_DIR / "config.yaml")

    target_col = col_config["target_column"]
    area_col = col_config["area_column"]
    date_col = col_config["date_column"]
    weather_col = col_config.get("weather_column", "Weather Conditions")

    # Locate dataset
    if data_path is None:
        csv_files = sorted(DATA_DIR.glob("*.csv"))
        if not csv_files:
            excel_files = sorted(DATA_DIR.glob("*.xlsx"))
            if not excel_files:
                raise FileNotFoundError(f"No traffic dataset file found in {DATA_DIR}")
            data_path = excel_files[0]
        else:
            data_path = csv_files[0]

    logger.info("Loading raw dataset from %s", data_path)
    if data_path.suffix.lower() == ".csv":
        df = pd.read_csv(data_path)
    else:
        df = pd.read_excel(data_path)

    initial_rows = len(df)
    logger.info("Initial row count: %d", initial_rows)

    # 1. Deduplication
    df_dedup = df.drop_duplicates()
    dedup_dropped = initial_rows - len(df_dedup)
    logger.info("Dropped %d duplicate rows", dedup_dropped)

    # 2. Parse dates
    df_dedup["parsed_date"] = pd.to_datetime(df_dedup[date_col], errors="coerce")
    invalid_dates = df_dedup["parsed_date"].isna().sum()
    if invalid_dates > 0:
        logger.warning("Dropped %d rows with unparseable dates", invalid_dates)
        df_dedup = df_dedup.dropna(subset=["parsed_date"])

    # 3. Validate target column exists and is numeric
    if target_col not in df_dedup.columns:
        raise ValueError(f"Target column '{target_col}' not found in dataset")

    df_dedup["target_raw"] = pd.to_numeric(df_dedup[target_col], errors="coerce")
    missing_target = df_dedup["target_raw"].isna().sum()
    if missing_target > 0:
        logger.warning("Dropped %d rows with missing or non-numeric target", missing_target)
        df_dedup = df_dedup.dropna(subset=["target_raw"])

    # 4. Target clipping (enforce >= 1.0)
    min_clip = float(model_config.get("target_min_clip", 1.00))
    max_clip = float(model_config.get("target_max_clip", 2.00))

    clipped_below = (df_dedup["target_raw"] < min_clip).sum()
    clipped_above = (df_dedup["target_raw"] > max_clip).sum()
    df_dedup["target"] = df_dedup["target_raw"].clip(lower=min_clip, upper=max_clip)

    logger.info(
        "Target clipping summary: %d rows clipped below %.2f, %d rows clipped above %.2f",
        clipped_below,
        min_clip,
        clipped_above,
        max_clip,
    )

    # 5. Prediction-Time Feature Engineering (Zero Leakage)
    holiday_checker = get_holiday_checker()

    df_dedup["date"] = df_dedup["parsed_date"].dt.date
    df_dedup["weekday"] = df_dedup["parsed_date"].dt.weekday
    df_dedup["is_weekend"] = (df_dedup["weekday"] >= 5).astype(int)
    df_dedup["month"] = df_dedup["parsed_date"].dt.month
    df_dedup["is_holiday"] = df_dedup["date"].apply(holiday_checker)

    # Clean Area and Weather strings
    df_dedup["area"] = df_dedup[area_col].astype(str).str.strip()
    if weather_col in df_dedup.columns:
        df_dedup["weather"] = df_dedup[weather_col].astype(str).str.strip().fillna("Clear")
    else:
        df_dedup["weather"] = "Clear"

    # Select only prediction-time features and target (strictly exclude all contemporaneous measurements)
    feature_cols = ["date", "area", "weather", "weekday", "is_weekend", "month", "is_holiday", "target"]
    clean_df = df_dedup[feature_cols].copy()

    # Sort chronologically for time-based splitting
    clean_df = clean_df.sort_values(by=["date", "area"]).reset_index(drop=True)

    summary = {
        "initial_rows": initial_rows,
        "final_rows": len(clean_df),
        "dedup_dropped": int(dedup_dropped),
        "invalid_dates_dropped": int(invalid_dates),
        "missing_target_dropped": int(missing_target),
        "clipped_below": int(clipped_below),
        "clipped_above": int(clipped_above),
        "min_date": str(clean_df["date"].min()),
        "max_date": str(clean_df["date"].max()),
        "distinct_areas": sorted(clean_df["area"].unique().tolist()),
        "distinct_weather": sorted(clean_df["weather"].unique().tolist()),
    }

    if save_cleaned:
        ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        out_csv = ARTIFACTS_DIR / "cleaned_data.csv"
        clean_df.to_csv(out_csv, index=False)
        logger.info("Saved cleaned dataset to %s (%d rows)", out_csv, len(clean_df))

    return clean_df, summary


if __name__ == "__main__":
    df, stats = prepare_dataset()
    print("Dataset Preparation Summary:")
    for k, v in stats.items():
        print(f"  {k}: {v}")
