import csv
import io
import json
import logging
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings

logger = logging.getLogger("smartroute.metrics")


def validate_days(days: Optional[int]) -> int:
    """Validate days parameter against METRICS_DEFAULT_DAYS and METRICS_MAX_DAYS."""
    d = days if days is not None else settings.METRICS_DEFAULT_DAYS
    if d < 1 or d > settings.METRICS_MAX_DAYS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Parameter 'days' must be between 1 and {settings.METRICS_MAX_DAYS}.",
        )
    return d


def escape_csv_cell(val: Any) -> str:
    """
    Sanitize text cell to prevent CSV Formula Injection in Excel/Sheets.
    Prepend a single quote if string begins with =, +, -, or @.
    """
    if val is None:
        return ""
    s = str(val)
    if s and s[0] in ("=", "+", "-", "@"):
        return "'" + s
    return s


def build_origin_filter(column_name: str, origin: str) -> str:
    """Build SQL WHERE snippet for data_origin filter (live, simulated, or all)."""
    norm = origin.lower().strip()
    if norm == "simulated":
        return f"AND ({column_name} = TRUE)"
    elif norm == "live":
        return f"AND ({column_name} IS NULL OR {column_name} = FALSE)"
    return ""  # "all" includes both


def get_model_info() -> Dict[str, Any]:
    """Read ml/artifacts/metrics.json and return model metadata, version, and performance."""
    metrics_path = Path(settings.BACKEND_DIR).parent / "ml" / "artifacts" / "metrics.json"
    if not metrics_path.exists():
        return {
            "model_available": False,
            "message": "Model metrics artifact not found",
        }

    try:
        with open(metrics_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        metrics = data.get("metrics", {})
        lgb = metrics.get("lightgbm", {})
        baseline = metrics.get("baseline", {})
        train_range = data.get("train_date_range", ["2022-01-01", "2024-03-19"])
        val_range = data.get("val_date_range", ["2024-03-20", "2024-08-09"])

        return {
            "model_available": True,
            "model_version": data.get("model_version", "v1.0.0"),
            "data_source": data.get("data_source", "kaggle-bangalore-city-traffic"),
            "dataset_name": data.get("file_name", "Banglore_traffic_Dataset.csv"),
            "date_range": f"{train_range[0]} to {val_range[-1]}",
            "model_mae": lgb.get("mae"),
            "model_r2": lgb.get("r2"),
            "baseline_mae": baseline.get("mae"),
            "baseline_r2": baseline.get("r2"),
            "model_beats_baseline": metrics.get("model_beats_baseline", False),
            "mae_improvement_pct": metrics.get("mae_improvement_pct", 0.0),
            "note": (
                "Estimates are computed from a historical open dataset of Bangalore traffic "
                "patterns and weather conditions. They represent offline statistical projections "
                "and do not reflect real-time live traffic sensor feeds."
            ),
        }
    except Exception as exc:
        logger.error(f"Error reading model metrics: {exc}", exc_info=True)
        return {
            "model_available": False,
            "error": str(exc),
        }


async def get_metrics_summary(
    session: AsyncSession,
    days: int,
    origin: str = "all",
) -> Dict[str, Any]:
    """
    Compute comprehensive incident and dispatch summary metrics using efficient SQL aggregations.
    Guarantees no division by zero (returns 0.0 for rates and null for medians/percentiles).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    inc_origin_filter = build_origin_filter("is_simulated", origin)
    disp_origin_filter = build_origin_filter("d.is_simulated", origin)

    # 1. Incidents SQL aggregate
    inc_query = text(f"""
        SELECT
            count(*) as total_reported,
            count(*) FILTER (WHERE status in ('validated', 'resolved') OR validated_at IS NOT NULL) as validated_count,
            count(*) FILTER (WHERE status = 'expired') as expired_count,
            count(*) FILTER (WHERE status = 'resolved') as resolved_count,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (validated_at - created_at)))
                FILTER (WHERE validated_at IS NOT NULL AND validated_at >= created_at) as med_val_time_s,
            PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (validated_at - created_at)))
                FILTER (WHERE validated_at IS NOT NULL AND validated_at >= created_at) as p90_val_time_s
        FROM incidents
        WHERE created_at >= :cutoff
        {inc_origin_filter}
    """)
    inc_res = await session.execute(inc_query, {"cutoff": cutoff})
    inc_row = inc_res.mappings().one()

    total_reported = int(inc_row["total_reported"] or 0)
    validated_count = int(inc_row["validated_count"] or 0)
    expired_count = int(inc_row["expired_count"] or 0)
    resolved_count = int(inc_row["resolved_count"] or 0)
    validation_rate = round(float(validated_count / total_reported), 4) if total_reported > 0 else 0.0

    med_val_time = round(float(inc_row["med_val_time_s"]), 1) if inc_row["med_val_time_s"] is not None else None
    p90_val_time = round(float(inc_row["p90_val_time_s"]), 1) if inc_row["p90_val_time_s"] is not None else None

    # 2. Dispatches SQL aggregate
    disp_query = text(f"""
        SELECT
            count(*) as total_offered,
            count(*) FILTER (WHERE d.status in ('accepted', 'en_route_to_scene', 'at_scene', 'to_hospital', 'completed') OR d.accepted_at IS NOT NULL) as accepted_count,
            count(*) FILTER (WHERE d.status = 'declined') as declined_count,
            count(*) FILTER (WHERE d.status = 'expired') as timed_out_count,
            -- validation to offer
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (d.offered_at - inc.validated_at)))
                FILTER (WHERE inc.validated_at IS NOT NULL AND d.offered_at >= inc.validated_at) as med_val_to_offer_s,
            PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (d.offered_at - inc.validated_at)))
                FILTER (WHERE inc.validated_at IS NOT NULL AND d.offered_at >= inc.validated_at) as p90_val_to_offer_s,
            -- offer to accept
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (d.accepted_at - d.offered_at)))
                FILTER (WHERE d.accepted_at IS NOT NULL AND d.accepted_at >= d.offered_at) as med_offer_to_accept_s,
            PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (d.accepted_at - d.offered_at)))
                FILTER (WHERE d.accepted_at IS NOT NULL AND d.accepted_at >= d.offered_at) as p90_offer_to_accept_s,
            -- accept to at_scene
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (d.arrived_at - d.accepted_at)))
                FILTER (WHERE d.arrived_at IS NOT NULL AND d.accepted_at IS NOT NULL AND d.arrived_at >= d.accepted_at) as med_accept_to_at_scene_s,
            PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (d.arrived_at - d.accepted_at)))
                FILTER (WHERE d.arrived_at IS NOT NULL AND d.accepted_at IS NOT NULL AND d.arrived_at >= d.accepted_at) as p90_accept_to_at_scene_s,
            -- at_scene to hospital arrival
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (d.completed_at - d.arrived_at)))
                FILTER (WHERE d.completed_at IS NOT NULL AND d.arrived_at IS NOT NULL AND d.completed_at >= d.arrived_at) as med_at_scene_to_hospital_s,
            PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (d.completed_at - d.arrived_at)))
                FILTER (WHERE d.completed_at IS NOT NULL AND d.arrived_at IS NOT NULL AND d.completed_at >= d.arrived_at) as p90_at_scene_to_hospital_s,
            -- total validation to at_scene
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (d.arrived_at - inc.validated_at)))
                FILTER (WHERE d.arrived_at IS NOT NULL AND inc.validated_at IS NOT NULL AND d.arrived_at >= inc.validated_at) as med_val_to_at_scene_s,
            PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (d.arrived_at - inc.validated_at)))
                FILTER (WHERE d.arrived_at IS NOT NULL AND inc.validated_at IS NOT NULL AND d.arrived_at >= inc.validated_at) as p90_val_to_at_scene_s
        FROM dispatches d
        LEFT JOIN incidents inc ON d.incident_id = inc.id
        WHERE d.offered_at >= :cutoff
        {disp_origin_filter}
    """)
    disp_res = await session.execute(disp_query, {"cutoff": cutoff})
    disp_row = disp_res.mappings().one()

    total_offered = int(disp_row["total_offered"] or 0)
    accepted_count = int(disp_row["accepted_count"] or 0)
    declined_count = int(disp_row["declined_count"] or 0)
    timed_out_count = int(disp_row["timed_out_count"] or 0)
    acceptance_rate = round(float(accepted_count / total_offered), 4) if total_offered > 0 else 0.0

    # 3. Manual dispatches needed
    manual_query = text(f"""
        SELECT count(DISTINCT incident_id) as manual_needed
        FROM dispatches d
        WHERE d.offered_at >= :cutoff
          AND d.offer_number >= :max_offers
          AND d.status in ('expired', 'declined')
        {disp_origin_filter}
    """)
    manual_res = await session.execute(manual_query, {
        "cutoff": cutoff,
        "max_offers": settings.DISPATCH_MAX_OFFERS_PER_INCIDENT,
    })
    manual_dispatches_needed = int(manual_res.scalar_one() or 0)

    # 4. Active ambulances now & availability
    amb_query = text("""
        SELECT
            count(*) as total_verified,
            count(*) FILTER (WHERE status != 'offline' AND (last_seen_at IS NOT NULL AND EXTRACT(EPOCH FROM (now() - last_seen_at)) <= :stale_s)) as active_now,
            count(*) FILTER (WHERE status = 'available' AND (last_seen_at IS NOT NULL AND EXTRACT(EPOCH FROM (now() - last_seen_at)) <= :stale_s)) as available_now
        FROM ambulances
        WHERE is_verified = TRUE
    """)
    amb_res = await session.execute(amb_query, {"stale_s": settings.AMBULANCE_LOCATION_STALE_S})
    amb_row = amb_res.mappings().one()

    total_verified = int(amb_row["total_verified"] or 0)
    active_now = int(amb_row["active_now"] or 0)
    available_now = int(amb_row["available_now"] or 0)
    avg_availability = round(float(available_now / total_verified), 4) if total_verified > 0 else 0.0

    def _val(k: str) -> Optional[float]:
        v = disp_row[k]
        return round(float(v), 1) if v is not None else None

    return {
        "data_origin": origin,
        "days": days,
        "incidents": {
            "reported": total_reported,
            "validated": validated_count,
            "rejected_or_expired": expired_count,
            "resolved": resolved_count,
            "validation_rate": validation_rate,
            "report_to_validation_time_s": {
                "median": med_val_time,
                "p90": p90_val_time,
            },
        },
        "dispatches": {
            "offered": total_offered,
            "accepted": accepted_count,
            "declined": declined_count,
            "timed_out": timed_out_count,
            "acceptance_rate": acceptance_rate,
            "manual_dispatches_needed": manual_dispatches_needed,
            "response_times_s": {
                "validation_to_offer": {
                    "median": _val("med_val_to_offer_s"),
                    "p90": _val("p90_val_to_offer_s"),
                },
                "offer_to_accept": {
                    "median": _val("med_offer_to_accept_s"),
                    "p90": _val("p90_offer_to_accept_s"),
                },
                "accept_to_at_scene": {
                    "median": _val("med_accept_to_at_scene_s"),
                    "p90": _val("p90_accept_to_at_scene_s"),
                },
                "at_scene_to_hospital": {
                    "median": _val("med_at_scene_to_hospital_s"),
                    "p90": _val("p90_at_scene_to_hospital_s"),
                },
                "total_validation_to_at_scene": {
                    "median": _val("med_val_to_at_scene_s"),
                    "p90": _val("p90_val_to_at_scene_s"),
                },
            },
        },
        "ambulances": {
            "active_now": active_now,
            "total_verified": total_verified,
            "average_availability": avg_availability,
        },
    }


async def get_metrics_timeseries(
    session: AsyncSession,
    days: int,
    bucket: str = "day",
    origin: str = "all",
) -> Dict[str, Any]:
    """Compute incident and dispatch counts aggregated per time bucket (hour or day)."""
    clean_bucket = "hour" if bucket.lower() == "hour" else "day"
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    inc_filter = build_origin_filter("is_simulated", origin)
    disp_filter = build_origin_filter("is_simulated", origin)

    # Aggregate incidents by bucket
    inc_query = text(f"""
        SELECT
            date_trunc(:bucket, created_at) as bucket_time,
            count(*) as count
        FROM incidents
        WHERE created_at >= :cutoff
        {inc_filter}
        GROUP BY bucket_time
        ORDER BY bucket_time ASC
    """)
    inc_res = await session.execute(inc_query, {"bucket": clean_bucket, "cutoff": cutoff})
    inc_map = {row["bucket_time"].isoformat(): int(row["count"]) for row in inc_res.mappings().all()}

    # Aggregate dispatches by bucket
    disp_query = text(f"""
        SELECT
            date_trunc(:bucket, offered_at) as bucket_time,
            count(*) as count
        FROM dispatches
        WHERE offered_at >= :cutoff
        {disp_filter}
        GROUP BY bucket_time
        ORDER BY bucket_time ASC
    """)
    disp_res = await session.execute(disp_query, {"bucket": clean_bucket, "cutoff": cutoff})
    disp_map = {row["bucket_time"].isoformat(): int(row["count"]) for row in disp_res.mappings().all()}

    all_keys = sorted(set(inc_map.keys()) | set(disp_map.keys()))
    points = [
        {
            "timestamp": k,
            "incidents": inc_map.get(k, 0),
            "dispatches": disp_map.get(k, 0),
        }
        for k in all_keys
    ]

    return {
        "data_origin": origin,
        "days": days,
        "bucket": clean_bucket,
        "points": points,
    }


async def get_metrics_hotspots(
    session: AsyncSession,
    days: int,
    origin: str = "all",
) -> Dict[str, Any]:
    """
    Cluster incidents into a HEATMAP_GRID_M grid using PostGIS ST_SnapToGrid on EPSG:3857.
    Returns cell center lat/lng, count, and the predominant incident type (mode).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    inc_filter = build_origin_filter("is_simulated", origin)
    grid_m = float(settings.HEATMAP_GRID_M)

    query = text(f"""
        SELECT
            ST_Y(ST_Transform(ST_Centroid(ST_SnapToGrid(ST_Transform(location::geometry, 3857), :grid_m)), 4326)) as lat,
            ST_X(ST_Transform(ST_Centroid(ST_SnapToGrid(ST_Transform(location::geometry, 3857), :grid_m)), 4326)) as lng,
            count(*) as count,
            MODE() WITHIN GROUP (ORDER BY incident_type) as top_type
        FROM incidents
        WHERE created_at >= :cutoff
        {inc_filter}
        GROUP BY ST_SnapToGrid(ST_Transform(location::geometry, 3857), :grid_m)
        ORDER BY count DESC
        LIMIT 500
    """)
    res = await session.execute(query, {"cutoff": cutoff, "grid_m": grid_m})
    rows = res.mappings().all()

    cells = [
        {
            "lat": round(float(r["lat"]), 5),
            "lng": round(float(r["lng"]), 5),
            "count": int(r["count"]),
            "top_type": str(r["top_type"]) if r["top_type"] is not None else "accident",
        }
        for r in rows
    ]

    return {
        "data_origin": origin,
        "days": days,
        "grid_m": grid_m,
        "total_cells": len(cells),
        "cells": cells,
    }


async def export_metrics_csv(
    session: AsyncSession,
    days: int,
    kind: str,
    origin: str = "all",
) -> str:
    """
    Generate CSV export for incidents or dispatches.
    - Coordinates rounded to 3 decimal places.
    - Absolutely NO user ids or emails included.
    - Escapes formula characters (=, +, -, @) to prevent CSV Injection.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    output = io.StringIO()
    writer = csv.writer(output)

    clean_kind = kind.lower().strip()
    if clean_kind == "dispatches":
        disp_filter = build_origin_filter("d.is_simulated", origin)
        query = text(f"""
            SELECT
                d.id as dispatch_id,
                d.status,
                d.emergency_type,
                d.offer_number,
                d.eta_to_scene_s,
                d.eta_to_hospital_s,
                d.offered_at,
                d.accepted_at,
                d.arrived_at,
                d.completed_at,
                d.is_simulated
            FROM dispatches d
            WHERE d.offered_at >= :cutoff
            {disp_filter}
            ORDER BY d.offered_at DESC
        """)
        res = await session.execute(query, {"cutoff": cutoff})
        rows = res.mappings().all()

        headers = [
            "dispatch_id",
            "status",
            "emergency_type",
            "offer_number",
            "eta_to_scene_s",
            "eta_to_hospital_s",
            "offered_at",
            "accepted_at",
            "arrived_at",
            "completed_at",
            "is_simulated",
        ]
        writer.writerow(headers)
        for r in rows:
            writer.writerow([
                escape_csv_cell(r["dispatch_id"]),
                escape_csv_cell(r["status"]),
                escape_csv_cell(r["emergency_type"]),
                escape_csv_cell(r["offer_number"]),
                escape_csv_cell(r["eta_to_scene_s"]),
                escape_csv_cell(r["eta_to_hospital_s"]),
                escape_csv_cell(r["offered_at"].isoformat() if r["offered_at"] else ""),
                escape_csv_cell(r["accepted_at"].isoformat() if r["accepted_at"] else ""),
                escape_csv_cell(r["arrived_at"].isoformat() if r["arrived_at"] else ""),
                escape_csv_cell(r["completed_at"].isoformat() if r["completed_at"] else ""),
                escape_csv_cell(bool(r["is_simulated"])),
            ])
    else:  # incidents
        inc_filter = build_origin_filter("is_simulated", origin)
        query = text(f"""
            SELECT
                id as incident_id,
                incident_type,
                status,
                confirmations,
                rejections,
                trust_score,
                ST_Y(location::geometry) as lat,
                ST_X(location::geometry) as lng,
                created_at,
                validated_at,
                resolved_at,
                is_simulated
            FROM incidents
            WHERE created_at >= :cutoff
            {inc_filter}
            ORDER BY created_at DESC
        """)
        res = await session.execute(query, {"cutoff": cutoff})
        rows = res.mappings().all()

        headers = [
            "incident_id",
            "incident_type",
            "status",
            "confirmations",
            "rejections",
            "trust_score",
            "latitude",
            "longitude",
            "created_at",
            "validated_at",
            "resolved_at",
            "is_simulated",
        ]
        writer.writerow(headers)
        for r in rows:
            lat = round(float(r["lat"]), 3) if r["lat"] is not None else ""
            lng = round(float(r["lng"]), 3) if r["lng"] is not None else ""
            writer.writerow([
                escape_csv_cell(r["incident_id"]),
                escape_csv_cell(r["incident_type"]),
                escape_csv_cell(r["status"]),
                escape_csv_cell(r["confirmations"]),
                escape_csv_cell(r["rejections"]),
                escape_csv_cell(r["trust_score"]),
                escape_csv_cell(lat),
                escape_csv_cell(lng),
                escape_csv_cell(r["created_at"].isoformat() if r["created_at"] else ""),
                escape_csv_cell(r["validated_at"].isoformat() if r["validated_at"] else ""),
                escape_csv_cell(r["resolved_at"].isoformat() if r["resolved_at"] else ""),
                escape_csv_cell(bool(r["is_simulated"])),
            ])

    return output.getvalue()
