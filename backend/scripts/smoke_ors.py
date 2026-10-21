import asyncio
import os
import sys
from pathlib import Path

# Add backend directory to sys.path so app modules are resolvable
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.services.ors_client import ors_client
from app.services.routing_service import routing_service
from app.services.geocode_service import geocode_service


async def run_smoke_test() -> None:
    """Run one real call to directions and one real call to geocoding using configured credentials."""
    print("=" * 60)
    print("SmartRoute AI - OpenRouteService / HeiGIT Live Smoke Test")
    print("=" * 60)
    print(f"Base URL: {settings.ORS_BASE_URL}")
    print(f"Directions Path: {settings.ORS_DIRECTIONS_PATH}")
    print(f"Geocode Search Path: {settings.ORS_GEOCODE_SEARCH_PATH}")

    key = settings.ORS_API_KEY.strip()
    if not key or key == "your_openrouteservice_api_key_here":
        print("\n[ERROR] ORS_API_KEY is not configured in .env. Please set a valid key to run smoke test.")
        sys.exit(1)

    masked_key = f"{key[:6]}...{key[-4:]}" if len(key) > 10 else "***"
    print(f"API Key: {masked_key} (length: {len(key)})")
    print("-" * 60)

    # 1. Real Directions Call (Bengaluru: Cubbon Park to Koramangala)
    origin = (12.9716, 77.5946)
    dest = (12.9352, 77.6245)
    print(f"\n[1/2] Testing Directions: {origin} -> {dest}...")
    try:
        route_resp = await routing_service.get_routes(origin=origin, destination=dest)
        print(f"  Status: SUCCESS")
        print(f"  Provider: {route_resp.provider}")
        print(f"  Routes found: {len(route_resp.routes)}")
        if route_resp.routes:
            p_route = route_resp.routes[0]
            print(f"  Primary Distance: {p_route.distance_m / 1000.0:.2f} km")
            print(f"  Primary Duration: {p_route.duration_s / 60.0:.1f} mins")
            print(f"  Coordinate points: {len(p_route.geometry.coordinates)}")
            if p_route.steps:
                print(f"  First Maneuver: {p_route.steps[0].instruction} ({p_route.steps[0].distance_m:.0f}m)")
        if route_resp.warning:
            print(f"  Warning: {route_resp.warning}")
    except Exception as exc:
        print(f"  Status: FAILED -> {type(exc).__name__}: {exc}")

    # 2. Real Geocode Forward Search Call
    query_text = "MG Road, Bengaluru"
    print(f"\n[2/2] Testing Geocoding Forward Search: '{query_text}'...")
    try:
        geo_resp = await geocode_service.search(query_text)
        print(f"  Status: SUCCESS")
        print(f"  Provider: {geo_resp.provider}")
        print(f"  Results found: {len(geo_resp.results)}")
        if geo_resp.results:
            top = geo_resp.results[0]
            print(f"  Top Match Label: {top.label}")
            print(f"  Coordinates: lat={top.lat}, lng={top.lng}")
            print(f"  Locality: {top.locality}")
    except Exception as exc:
        print(f"  Status: FAILED -> {type(exc).__name__}: {exc}")

    print("\n" + "=" * 60)
    print("Smoke test finished.")
    print("=" * 60)


async def _async_main() -> None:
    try:
        await run_smoke_test()
    finally:
        await ors_client.close()
        await asyncio.sleep(0.1)


def main() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
