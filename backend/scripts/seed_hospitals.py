"""
OpenStreetMap Hospital Seeder for SmartRoute AI.
Queries the Overpass API for hospitals in Bengaluru, caches the response,
maps OSM healthcare tags to emergency types, and upserts hospitals idempotently into PostGIS.
NOTE: Bed capacity numbers are strictly SIMULATED for demonstration.
Data source: OpenStreetMap contributors (ODbL license).
"""
import asyncio
import json
import logging
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import httpx
from geoalchemy2.elements import WKTElement
from sqlalchemy import select

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.models.hospital import Hospital

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_hospitals")

DATA_DIR = BACKEND_DIR / "data"
CACHE_FILE = DATA_DIR / "overpass_hospitals.json"


def map_osm_tags_to_emergency_types(tags: Dict[str, str]) -> List[str]:
    """
    Map OpenStreetMap tags and name strings to emergency types:
    general, trauma, cardiac, burns, maternity, pediatric.
    """
    text_corpus = " ".join([
        tags.get("name", ""),
        tags.get("healthcare:speciality", ""),
        tags.get("speciality", ""),
        tags.get("description", ""),
        tags.get("operator", ""),
    ]).lower()

    types = set()

    # Trauma & Critical Care
    if any(k in text_corpus for k in ["trauma", "casualty", "accident", "emergency", "ortho"]):
        types.add("trauma")

    # Cardiac
    if any(k in text_corpus for k in ["cardio", "heart", "coronary", "vascular"]):
        types.add("cardiac")

    # Burns
    if any(k in text_corpus for k in ["burn", "plastic surgery"]):
        types.add("burns")

    # Maternity
    if any(k in text_corpus for k in ["maternity", "women", "mother", "gynae", "obstetric"]):
        types.add("maternity")

    # Pediatric
    if any(k in text_corpus for k in ["pediatric", "child", "children", "neonatal", "infant"]):
        types.add("pediatric")

    # General is default baseline for any hospital
    types.add("general")

    return sorted(list(types))


def fetch_overpass_data() -> Dict[str, Any]:
    """Fetch hospitals within Bengaluru bounding box from Overpass or load from local cache."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if CACHE_FILE.exists() and CACHE_FILE.stat().st_size > 0:
        logger.info("Found cached Overpass response at %s", CACHE_FILE)
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning("Could not read cache file %s: %s. Re-querying Overpass...", CACHE_FILE, exc)

    min_lat, min_lng, max_lat, max_lng = settings.BENGALURU_BBOX
    # Overpass bounding box format: (south, west, north, east)
    query = f"""
    [out:json][timeout:35];
    (
      node["amenity"="hospital"]({min_lat},{min_lng},{max_lat},{max_lng});
      way["amenity"="hospital"]({min_lat},{min_lng},{max_lat},{max_lng});
      relation["amenity"="hospital"]({min_lat},{min_lng},{max_lat},{max_lng});
    );
    out center;
    """

    headers = {
        "User-Agent": "SmartRoute-AI/0.1.0 (emergency routing system; contact: support@smartroute.ai)",
    }

    logger.info("Querying Overpass API at %s for Bengaluru bbox %s...", settings.OVERPASS_URL, settings.BENGALURU_BBOX)
    try:
        with httpx.Client(timeout=45.0) as client:
            resp = client.post(settings.OVERPASS_URL, data={"data": query}, headers=headers)
            if resp.status_code == 429:
                logger.error("Overpass API rate limit exceeded (HTTP 429). Please retry after a brief pause.")
                raise RuntimeError("Overpass rate limit reached")
            if resp.status_code >= 500:
                logger.error("Overpass API server busy (HTTP %d). Please retry shortly.", resp.status_code)
                raise RuntimeError("Overpass server unavailable")
            resp.raise_for_status()
            data = resp.json()

            # Cache the response
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.info("Cached Overpass response (%d elements) to %s", len(data.get("elements", [])), CACHE_FILE)
            return data
    except Exception as exc:
        logger.error("Failed to fetch hospital data from Overpass: %s", exc)
        raise


async def seed_hospitals(overpass_data: Dict[str, Any]) -> None:
    """Upsert hospitals into PostGIS database."""
    elements = overpass_data.get("elements", [])
    logger.info("Processing %d elements from Overpass...", len(elements))

    inserted = 0
    updated = 0
    skipped = 0

    random.seed(42)  # Deterministic simulated beds for consistency across runs

    async with AsyncSessionLocal() as session:
        for el in elements:
            tags = el.get("tags", {})
            name = tags.get("name", "").strip()

            # Skip entries without a name
            if not name:
                skipped += 1
                continue

            # Extract coordinates
            lat: Optional[float] = None
            lng: Optional[float] = None

            if el.get("type") == "node":
                lat = el.get("lat")
                lng = el.get("lon")
            elif "center" in el:
                center = el["center"]
                lat = center.get("lat")
                lng = center.get("lon")

            if lat is None or lng is None:
                skipped += 1
                continue

            osm_id = f"{el.get('type')}/{el.get('id')}"
            phone = tags.get("phone") or tags.get("contact:phone")
            address_parts = [
                tags.get("addr:housenumber"),
                tags.get("addr:street"),
                tags.get("addr:suburb") or tags.get("addr:neighbourhood"),
                tags.get("addr:city", "Bengaluru"),
                tags.get("addr:postcode"),
            ]
            address = ", ".join([p for p in address_parts if p]) or tags.get("address")

            has_emergency = tags.get("emergency") == "yes" or True
            opening_hours = tags.get("opening_hours", "").strip()
            is_24x7 = True if opening_hours == "24/7" else (False if opening_hours else None)

            emergency_types = map_osm_tags_to_emergency_types(tags)
            sim_beds = random.randint(8, 40)
            point_geom = WKTElement(f"POINT({lng} {lat})", srid=4326)

            # Check if exists by osm_id
            stmt = select(Hospital).where(Hospital.osm_id == osm_id)
            res = await session.execute(stmt)
            existing = res.scalar_one_or_none()

            if existing is not None:
                existing.name = name
                existing.location = point_geom
                existing.phone = phone
                existing.address = address
                existing.has_emergency = has_emergency
                existing.emergency_types = emergency_types
                existing.is_24x7 = is_24x7
                existing.beds_simulated = True
                existing.source = "osm"
                existing.osm_attribution = "© OpenStreetMap contributors"
                updated += 1
            else:
                new_hospital = Hospital(
                    name=name,
                    location=point_geom,
                    phone=phone,
                    address=address,
                    has_emergency=has_emergency,
                    specialties=emergency_types,
                    emergency_types=emergency_types,
                    simulated_beds=sim_beds,
                    beds_simulated=True,
                    is_24x7=is_24x7,
                    source="osm",
                    osm_attribution="© OpenStreetMap contributors",
                    osm_id=osm_id,
                )
                session.add(new_hospital)
                inserted += 1

        await session.commit()

    logger.info("==================================================")
    logger.info("HOSPITAL SEEDING SUMMARY")
    logger.info("==================================================")
    logger.info("Inserted : %d", inserted)
    logger.info("Updated  : %d", updated)
    logger.info("Skipped  : %d", skipped)
    logger.info("Total    : %d", inserted + updated)
    logger.info("Attribution: Data © OpenStreetMap contributors (ODbL).")
    logger.info("Notice     : Emergency bed capacity is strictly SIMULATED.")
    logger.info("==================================================")


async def _async_main() -> None:
    try:
        data = fetch_overpass_data()
        await seed_hospitals(data)
    finally:
        await engine.dispose()
        await asyncio.sleep(0.1)


def main() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
