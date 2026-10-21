"""
Incident-aware routing, spatial delay penalties, avoid-polygon generation, and ranking.
"""
import hashlib
import json
import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.functions import ST_DWithin, ST_GeogFromText

from app.core.config import settings
from app.models.incident import Incident, IncidentStatus, IncidentType
from app.services.incident_service import extract_incident_lat_lng
from app.services.realtime import haversine_distance_m
from app.schemas.routing import (
    IncidentOnRoute,
    RouteItem,
    RouteResponse,
    RouteSummary,
)

logger = logging.getLogger("smartroute.routing.incidents")


def distance_from_point_to_linestring_m(
    point_lat: float,
    point_lng: float,
    coords: List[List[float]],
) -> float:
    """
    Compute planar-projected distance in meters from (point_lat, point_lng)
    to a GeoJSON LineString [ [lng1, lat1], [lng2, lat2], ... ].
    """
    if not coords:
        return float("inf")
    if len(coords) == 1:
        return haversine_distance_m(point_lat, point_lng, coords[0][1], coords[0][0])

    meters_per_deg_lat = 111132.95
    rad_lat = math.radians(point_lat)
    meters_per_deg_lng = 111412.84 * math.cos(rad_lat)

    min_dist_m = float("inf")

    for i in range(len(coords) - 1):
        p1_lng, p1_lat = coords[i][0], coords[i][1]
        p2_lng, p2_lat = coords[i + 1][0], coords[i + 1][1]

        x1 = (p1_lng - point_lng) * meters_per_deg_lng
        y1 = (p1_lat - point_lat) * meters_per_deg_lat
        x2 = (p2_lng - point_lng) * meters_per_deg_lng
        y2 = (p2_lat - point_lat) * meters_per_deg_lat

        dx = x2 - x1
        dy = y2 - y1
        length_sq = dx * dx + dy * dy

        if length_sq < 1e-6:
            dist = math.sqrt(x1 * x1 + y1 * y1)
        else:
            t = -(x1 * dx + y1 * dy) / length_sq
            t = max(0.0, min(1.0, t))
            proj_x = x1 + t * dx
            proj_y = y1 + t * dy
            dist = math.sqrt(proj_x * proj_x + proj_y * proj_y)

        if dist < min_dist_m:
            min_dist_m = dist

    return min_dist_m



async def get_active_corridor_incidents(
    db: AsyncSession,
    origin: Tuple[float, float],
    destination: Tuple[float, float],
) -> List[Tuple[Incident, float, float]]:
    """
    Fetch active, unexpired incidents within the spatial corridor between origin and destination.
    Uses PostGIS spatial index with a generous search radius around the route midpoint.
    Returns: List of (Incident, lat, lng).
    """
    orig_lat, orig_lng = origin
    dest_lat, dest_lng = destination

    mid_lat = (orig_lat + dest_lat) / 2.0
    mid_lng = (orig_lng + dest_lng) / 2.0
    direct_dist_m = haversine_distance_m(orig_lat, orig_lng, dest_lat, dest_lng)
    # Search radius covers the direct corridor plus detours
    search_radius_m = max(10000.0, direct_dist_m * 0.8)

    now = datetime.now(timezone.utc)
    mid_point_wkt = f"SRID=4326;POINT({mid_lng} {mid_lat})"

    stmt = (
        select(Incident)
        .where(
            Incident.status.in_([IncidentStatus.pending, IncidentStatus.validated]),
            Incident.expires_at > now,
            ST_DWithin(Incident.location, ST_GeogFromText(mid_point_wkt), search_radius_m),
        )
    )

    result = await db.execute(stmt)
    incidents = result.scalars().all()

    items: List[Tuple[Incident, float, float]] = []
    for inc in incidents:
        try:
            lat, lng = extract_incident_lat_lng(inc.location)
            items.append((inc, lat, lng))
        except Exception as exc:
            logger.warning("Could not extract coords for incident %s: %s", inc.id, exc)

    return items


def hash_incidents_state(corridor_incidents: List[Tuple[Incident, float, float]]) -> str:
    """
    Generate an alphanumeric hash representing active incidents and their validation statuses.
    Ensures that cache invalidates whenever an incident status or set changes.
    """
    if not corridor_incidents:
        return "none"
    state_tuples = sorted([(str(inc.id), inc.status.value) for inc, _, _ in corridor_incidents])
    state_json = json.dumps(state_tuples, sort_keys=True)
    return hashlib.sha256(state_json.encode("utf-8")).hexdigest()[:12]


def find_incidents_on_route(
    route_coords: List[List[float]],
    corridor_incidents: List[Tuple[Incident, float, float]],
    buffer_m: float,
) -> Tuple[List[IncidentOnRoute], float]:
    """
    Identify incidents within buffer_m of route LineString and calculate delay penalty.
    Each incident is counted at most once per route.
    Returns: (list of IncidentOnRoute, estimated_delay_s).
    """
    incidents_on_route: List[IncidentOnRoute] = []
    total_delay_s = 0.0
    seen_ids = set()

    for inc, lat, lng in corridor_incidents:
        inc_id = str(inc.id)
        if inc_id in seen_ids:
            continue

        dist_m = distance_from_point_to_linestring_m(lat, lng, route_coords)
        if dist_m <= buffer_m:
            seen_ids.add(inc_id)
            incidents_on_route.append(
                IncidentOnRoute(
                    id=inc_id,
                    type=inc.incident_type.value,
                    status=inc.status.value,
                    lat=lat,
                    lng=lng,
                    distance_from_route_m=round(dist_m, 1),
                )
            )

            # Delay penalty calculation
            if inc.incident_type == IncidentType.accident:
                base_penalty = settings.PENALTY_ACCIDENT_S
            elif inc.incident_type == IncidentType.blockage:
                base_penalty = settings.PENALTY_BLOCKAGE_S
            else:
                base_penalty = settings.PENALTY_HAZARD_S

            weight = 1.0 if inc.status == IncidentStatus.validated else settings.PENDING_INCIDENT_WEIGHT
            total_delay_s += base_penalty * weight

    return incidents_on_route, round(total_delay_s, 1)


def create_circle_polygon_coords(
    lat: float,
    lng: float,
    radius_m: float,
    num_points: int = 16,
) -> List[List[List[float]]]:
    """
    Generate GeoJSON Polygon coordinates approximating a circle of radius_m.
    Format: [ [ [lng1, lat1], [lng2, lat2], ..., [lng1, lat1] ] ]
    """
    lat_deg_per_m = 1.0 / 111132.95
    lng_deg_per_m = 1.0 / (111412.84 * math.cos(math.radians(lat)))

    ring: List[List[float]] = []
    for i in range(num_points):
        angle = (2.0 * math.pi * i) / num_points
        d_lat = radius_m * math.cos(angle) * lat_deg_per_m
        d_lng = radius_m * math.sin(angle) * lng_deg_per_m
        ring.append([round(lng + d_lng, 6), round(lat + d_lat, 6)])
    ring.append(ring[0])  # Explicitly close linear ring

    return [ring]


def build_avoid_multipolygon(
    validated_incidents_on_fastest: List[IncidentOnRoute],
    origin: Tuple[float, float],
    destination: Tuple[float, float],
    radius_m: float,
    max_count: int,
) -> Optional[Dict[str, Any]]:
    """
    Build GeoJSON MultiPolygon of avoid circles around validated incidents on the fastest route.
    Safely drops polygons if the origin or destination lies inside the avoid circle.
    """
    orig_lat, orig_lng = origin
    dest_lat, dest_lng = destination

    safe_incidents = []
    for inc in validated_incidents_on_fastest:
        dist_orig = haversine_distance_m(orig_lat, orig_lng, inc.lat, inc.lng)
        dist_dest = haversine_distance_m(dest_lat, dest_lng, inc.lat, inc.lng)
        # Drop avoid circle if it engulfs origin or destination point
        if dist_orig <= radius_m or dist_dest <= radius_m:
            logger.info("Dropping avoid circle around %s (too close to origin/dest)", inc.id)
            continue
        safe_incidents.append(inc)

    if not safe_incidents:
        return None

    # Limit to maximum allowed avoid polygons
    target_incidents = safe_incidents[:max_count]
    polygon_list = [create_circle_polygon_coords(inc.lat, inc.lng, radius_m) for inc in target_incidents]

    return {
        "type": "MultiPolygon",
        "coordinates": polygon_list,
    }


def are_routes_near_duplicates(r1: RouteItem, r2: RouteItem) -> bool:
    """Check if two routes have nearly identical distances and durations (< 1% difference)."""
    # Exact coordinates match
    if r1.geometry.coordinates == r2.geometry.coordinates:
        return True

    dist_diff = abs(r1.distance_m - r2.distance_m) / max(r1.distance_m, 1.0)
    dur_diff = abs(r1.duration_s - r2.duration_s) / max(r1.duration_s, 1.0)
    return dist_diff < 0.01 and dur_diff < 0.01


def generate_route_reason(
    route: RouteItem,
    rank: int,
    raw_fastest_adjusted_duration: float,
    avoided_count: int = 0,
) -> str:
    """Generate concise human-readable explanation for route ranking."""
    if route.avoids_incidents:
        count_str = f"{avoided_count} reported incident(s)" if avoided_count > 0 else "reported incidents"
        if rank == 1 and raw_fastest_adjusted_duration > route.adjusted_duration_s:
            saved_min = max(1, round((raw_fastest_adjusted_duration - route.adjusted_duration_s) / 60))
            return f"Avoids {count_str}, estimated {saved_min} min faster than the fastest raw route"
        return f"Avoids {count_str}"

    traffic_factor = getattr(route, "traffic_factor", 1.0)
    has_traffic = traffic_factor > 1.05
    pct = int(round((traffic_factor - 1.0) * 100))

    if not route.incidents_on_route:
        if has_traffic:
            if rank == 1:
                return f"Fastest route, ~{pct}% slower than free-flow due to predicted traffic"
            return f"~{pct}% slower than free-flow due to predicted traffic"
        return "No incidents on this route"

    delay_min = max(1, round(route.estimated_delay_s / 60))
    count = len(route.incidents_on_route)
    incident_label = "incident" if count == 1 else "incidents"
    if has_traffic:
        return f"+{delay_min} min estimated delay from {count} reported {incident_label}, ~{pct}% slower from traffic"
    return f"+{delay_min} min estimated delay from {count} reported {incident_label}"
