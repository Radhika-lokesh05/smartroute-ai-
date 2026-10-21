"""
Dataset inspection script for SmartRoute AI traffic model.
Loads real Bengaluru traffic dataset (.csv or .xlsx) from ml/data and generates
a comprehensive inspection report saved to ml/artifacts/data_report.md.
Supports standard csv without external dependencies, with openpyxl/pandas if installed.
"""
import csv
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ML_DIR = Path(__file__).resolve().parent
DATA_DIR = ML_DIR / "data"
ARTIFACTS_DIR = ML_DIR / "artifacts"


def find_dataset_file() -> Optional[Path]:
    """Search for a .csv or .xlsx dataset file in ml/data."""
    if not DATA_DIR.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        return None

    for ext in ("*.csv", "*.xlsx", "*.xls"):
        matches = sorted(DATA_DIR.glob(ext))
        if matches:
            return matches[0]
    return None


def inspect_dataset() -> Tuple[bool, str]:
    """Inspect dataset file and generate data_report.md."""
    dataset_path = find_dataset_file()
    if not dataset_path:
        return False, "No dataset file (.csv or .xlsx) found in ml/data."

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    sheet_used = "N/A (CSV format)"
    rows: List[Dict[str, str]] = []
    columns: List[str] = []

    if dataset_path.suffix.lower() == ".csv":
        with open(dataset_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header:
                return False, "Dataset file is empty."
            columns = [c.strip() for c in header]
            for row in reader:
                if not row or all(not cell.strip() for cell in row):
                    continue
                row_dict = {}
                for idx, col_name in enumerate(columns):
                    row_dict[col_name] = row[idx].strip() if idx < len(row) else ""
                rows.append(row_dict)
    else:
        # Excel format
        try:
            import openpyxl
            wb = openpyxl.load_workbook(dataset_path, read_only=True, data_only=True)
            sheet_names = wb.sheetnames
            sheet_used = sheet_names[0]
            ws = wb[sheet_used]
            iter_rows = ws.iter_rows(values_only=True)
            header = next(iter_rows, None)
            columns = [str(c).strip() for c in header if c is not None]
            for r in iter_rows:
                if not r or all(c is None for c in r):
                    continue
                row_dict = {columns[idx]: str(val).strip() if val is not None else "" for idx, val in enumerate(r) if idx < len(columns)}
                rows.append(row_dict)
        except Exception as exc:
            return False, f"Failed to read Excel file {dataset_path}: {exc}. Please install openpyxl."

    row_count = len(rows)
    report: List[str] = []
    report.append("# Bengaluru Traffic Dataset Inspection Report\n")
    report.append(f"- **Dataset File**: `{dataset_path.name}`")
    report.append(f"- **Sheet Used**: `{sheet_used}`")
    report.append(f"- **Total Rows**: {row_count:,}")
    report.append(f"- **Total Columns**: {len(columns)}\n")

    # Missing values and types
    report.append("## 1. Column Inventory & Missing Values\n")
    report.append("| Column Name | Inferred Type | Missing Count | Missing % | Sample Value |")
    report.append("| :--- | :--- | :--- | :--- | :--- |")

    col_stats: Dict[str, Dict[str, Any]] = {}
    for col in columns:
        vals = [r[col] for r in rows if r.get(col, "") != ""]
        missing_count = row_count - len(vals)
        missing_pct = (missing_count / row_count * 100.0) if row_count > 0 else 0.0

        # Type inference
        is_num = True
        num_vals: List[float] = []
        for v in vals:
            try:
                num_vals.append(float(v))
            except ValueError:
                is_num = False
                break

        inferred_type = "Numeric (Float/Int)" if (is_num and vals) else "String / Categorical"
        sample_val = vals[0] if vals else "N/A"
        report.append(f"| `{col}` | {inferred_type} | {missing_count:,} | {missing_pct:.1f}% | `{sample_val}` |")
        col_stats[col] = {
            "type": inferred_type,
            "missing": missing_count,
            "values": num_vals if is_num else vals,
            "is_num": is_num,
        }
    report.append("")

    # Temporal analysis
    report.append("## 2. Temporal Granularity & Date Range\n")
    date_col = next((c for c in columns if "date" in c.lower()), None)
    time_col = next((c for c in columns if "time" in c.lower() and "travel" not in c.lower() and "date" not in c.lower()), None)

    min_date = None
    max_date = None
    has_time_of_day = False
    granularity = "Daily"

    if date_col:
        parsed_dates = []
        for r in rows:
            val = r.get(date_col, "")
            if val:
                for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"):
                    try:
                        dt = datetime.strptime(val, fmt)
                        parsed_dates.append(dt)
                        if dt.hour != 0 or dt.minute != 0 or dt.second != 0:
                            has_time_of_day = True
                        break
                    except ValueError:
                        pass
        if parsed_dates:
            min_date = min(parsed_dates).strftime("%Y-%m-%d")
            max_date = max(parsed_dates).strftime("%Y-%m-%d")

    if time_col:
        has_time_of_day = True
        granularity = "Hourly / Sub-daily"

    report.append(f"- **Primary Date Column**: `{date_col}`")
    report.append(f"- **Date Range**: {min_date} to {max_date}")
    report.append(f"- **Time-of-Day Column Exists**: {has_time_of_day} (Separate time column: {time_col})")
    report.append(f"- **Dataset Granularity**: **{granularity}** (One observation per road/area per date)\n")

    # Areas and Roads
    report.append("## 3. Geographical Entities (Areas & Roads)\n")
    area_col = next((c for c in columns if "area" in c.lower()), None)
    road_col = next((c for c in columns if "road" in c.lower() or "intersection" in c.lower() or "junction" in c.lower()), None)

    if area_col:
        area_counts: Dict[str, int] = {}
        for r in rows:
            a = r.get(area_col, "Unknown")
            area_counts[a] = area_counts.get(a, 0) + 1
        sorted_areas = sorted(area_counts.items(), key=lambda x: x[1], reverse=True)
        report.append(f"### Distinct Areas ({len(sorted_areas)}):\n")
        report.append("| Area Name | Observation Count | Share % |")
        report.append("| :--- | :--- | :--- |")
        for area, cnt in sorted_areas:
            pct = cnt / row_count * 100.0
            report.append(f"| `{area}` | {cnt:,} | {pct:.1f}% |")
        report.append("")

    if road_col:
        road_counts: Dict[str, int] = {}
        for r in rows:
            rd = r.get(road_col, "Unknown")
            road_counts[rd] = road_counts.get(rd, 0) + 1
        sorted_roads = sorted(road_counts.items(), key=lambda x: x[1], reverse=True)
        report.append(f"### Distinct Roads / Corridors ({len(sorted_roads)}):\n")
        report.append("| Road / Intersection | Observation Count | Share % |")
        report.append("| :--- | :--- | :--- |")
        for road, cnt in sorted_roads:
            pct = cnt / row_count * 100.0
            report.append(f"| `{road}` | {cnt:,} | {pct:.1f}% |")
        report.append("")

    # Weather analysis
    report.append("## 4. Weather Conditions\n")
    weather_col = next((c for c in columns if "weather" in c.lower()), None)
    if weather_col:
        weather_counts: Dict[str, int] = {}
        for r in rows:
            w = r.get(weather_col, "Unknown")
            weather_counts[w] = weather_counts.get(w, 0) + 1
        sorted_weather = sorted(weather_counts.items(), key=lambda x: x[1], reverse=True)
        report.append(f"- **Weather Column**: `{weather_col}`")
        report.append(f"- **Distinct Weather Conditions**: {len(sorted_weather)}\n")
        report.append("| Weather Condition | Count | Share % |")
        report.append("| :--- | :--- | :--- |")
        for cond, cnt in sorted_weather:
            pct = cnt / row_count * 100.0
            report.append(f"| `{cond}` | {cnt:,} | {pct:.1f}% |")
        report.append("")
    else:
        report.append("- **No weather column detected.**\n")

    # Metrics Summary: Speed, Travel Time Index, Congestion Level
    report.append("## 5. Traffic & Congestion Metrics Distribution\n")
    report.append("| Metric Column | Min | Mean | Max | Std Dev | Non-null Count |")
    report.append("| :--- | :--- | :--- | :--- | :--- | :--- |")

    candidate_metrics = ["Average Speed", "Travel Time Index", "Congestion Level", "Road Capacity Utilization"]
    for m in candidate_metrics:
        matched_col = next((c for c in columns if m.lower() in c.lower()), None)
        if matched_col and col_stats.get(matched_col, {}).get("is_num"):
            vals = col_stats[matched_col]["values"]
            if vals:
                min_v = min(vals)
                max_v = max(vals)
                mean_v = sum(vals) / len(vals)
                var_v = sum((x - mean_v) ** 2 for x in vals) / len(vals)
                std_v = math.sqrt(var_v)
                report.append(f"| `{matched_col}` | {min_v:.2f} | {mean_v:.2f} | {max_v:.2f} | {std_v:.2f} | {len(vals):,} |")
    report.append("")

    full_md = "\n".join(report)
    out_path = ARTIFACTS_DIR / "data_report.md"
    out_path.write_text(full_md, encoding="utf-8")
    return True, full_md


if __name__ == "__main__":
    success, output = inspect_dataset()
    print(output)
