"""
Ambulance Telemetry Simulator for SmartRoute AI.
Simulates a live emergency ambulance moving towards a destination, broadcasting
its coordinates over WebSocket so the frontend displays live proximity warnings.

Usage:
    python scripts/simulate_ambulance.py [--token <JWT>] [--lat <LAT>] [--lng <LNG>] [--speed <SPEED_KMH>]
"""
import argparse
import asyncio
import json
import math
import sys
import urllib.request
import urllib.error
from pathlib import Path

# Automatically resolve backend virtualenv site-packages if running from global python
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
venv_sites = [
    WORKSPACE_ROOT / "backend" / "venv" / "Lib" / "site-packages",
    WORKSPACE_ROOT / "backend" / ".venv" / "Lib" / "site-packages",
    WORKSPACE_ROOT / "venv" / "Lib" / "site-packages",
]
for p in venv_sites:
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

try:
    import websockets
except ImportError:
    print("\n[simulator] ERROR: 'websockets' library is required.")
    print("Please run this script using the backend virtual environment:")
    print("   .\\backend\\venv\\Scripts\\python scripts/simulate_ambulance.py")
    print("Or install websockets in your active python: pip install websockets\n")
    sys.exit(1)

DEFAULT_API_URL = "http://127.0.0.1:8000"
DEFAULT_WS_URL = "ws://127.0.0.1:8000/ws"

# Bengaluru center coordinates
DEFAULT_LAT = 12.9716
DEFAULT_LNG = 77.5946


def haversine_offset(lat: float, lng: float, bearing_deg: float, distance_m: float) -> tuple[float, float]:
    """Compute new lat/lng given bearing and distance in meters."""
    R = 6371000.0
    rad_lat = math.radians(lat)
    rad_lng = math.radians(lng)
    rad_bearing = math.radians(bearing_deg)
    d_div_r = distance_m / R

    new_lat = math.asin(
        math.sin(rad_lat) * math.cos(d_div_r)
        + math.cos(rad_lat) * math.sin(d_div_r) * math.cos(rad_bearing)
    )
    new_lng = rad_lng + math.atan2(
        math.sin(rad_bearing) * math.sin(d_div_r) * math.cos(rad_lat),
        math.cos(d_div_r) - math.sin(rad_lat) * math.sin(new_lat)
    )
    return math.degrees(new_lat), math.degrees(new_lng)


def obtain_token(email: str, password: str, api_url: str) -> str:
    """Authenticate and obtain JWT access token using standard library urllib."""
    login_url = f"{api_url.rstrip('/')}/api/auth/login"
    payload = json.dumps({"email": email, "password": password}).encode("utf-8")
    req = urllib.request.Request(
        login_url,
        data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["access_token"]
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8", errors="replace")
        print(f"[simulator] Authentication failed for {email} (HTTP {err.code}): {body}")
        sys.exit(1)
    except Exception as exc:
        print(f"[simulator] Failed to connect to {login_url}: {exc}")
        print("Please ensure the FastAPI backend is running: uvicorn app.main:app --reload --host 127.0.0.1 --port 8000")
        sys.exit(1)


async def run_simulation(
    ws_url: str,
    token: str,
    target_lat: float,
    target_lng: float,
    start_distance_m: float = 2000.0,
    speed_mps: float = 15.0,  # ~54 km/h
    step_interval_s: float = 2.0,
) -> None:
    print(f"[simulator] Connecting to WebSocket at {ws_url}...")
    async with websockets.connect(ws_url) as ws:
        # Step 1: Authenticate
        await ws.send(json.dumps({"type": "auth", "token": token}))
        auth_ack = json.loads(await ws.recv())
        if auth_ack.get("type") != "auth.success":
            print(f"[simulator] WebSocket authentication failed: {auth_ack}")
            return
        print("[simulator] Connected and authenticated successfully.")

        # Simulate approaching from the south-west (225 degrees)
        bearing = 45.0  # moving North-East towards target
        current_distance = start_distance_m

        print(f"[simulator] Simulating ambulance moving towards ({target_lat}, {target_lng}) from {start_distance_m}m...")
        print(f"[simulator] Step interval: {step_interval_s}s, Speed: {speed_mps * 3.6:.1f} km/h")

        step = 0
        while current_distance > 50.0:
            step += 1
            # Current ambulance location
            amb_lat, amb_lng = haversine_offset(target_lat, target_lng, bearing + 180.0, current_distance)

            payload = {
                "type": "ambulance.location",
                "lat": round(amb_lat, 6),
                "lng": round(amb_lng, 6),
                "heading": round(bearing, 1),
                "speed": round(speed_mps, 1),
            }

            await ws.send(json.dumps(payload))
            print(f"  Step {step:02d}: Sent location ({payload['lat']}, {payload['lng']}), distance to target: {int(current_distance)}m")

            # Move forward
            current_distance = max(0.0, current_distance - (speed_mps * step_interval_s))
            await asyncio.sleep(step_interval_s)

        print("[simulator] Ambulance arrived at destination vicinity. Simulation complete.")


def main():
    parser = argparse.ArgumentParser(description="SmartRoute AI Ambulance Proximity Simulator")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="Backend HTTP API URL")
    parser.add_argument("--ws-url", default=DEFAULT_WS_URL, help="Backend WebSocket URL")
    parser.add_argument("--token", help="JWT access token (if omitted, logs in with admin credentials)")
    parser.add_argument("--email", default="admin@smartroute.ai", help="Account email if token not provided")
    parser.add_argument("--password", default="adminpassword123", help="Account password if token not provided")
    parser.add_argument("--lat", type=float, default=DEFAULT_LAT, help="Target location latitude")
    parser.add_argument("--lng", type=float, default=DEFAULT_LNG, help="Target location longitude")
    parser.add_argument("--distance", type=float, default=2000.0, help="Starting distance in meters")

    args = parser.parse_args()

    token = args.token
    if not token:
        print(f"[simulator] Logging in as {args.email} to obtain JWT token...")
        token = obtain_token(args.email, args.password, args.api_url)

    try:
        asyncio.run(run_simulation(
            ws_url=args.ws_url,
            token=token,
            target_lat=args.lat,
            target_lng=args.lng,
            start_distance_m=args.distance,
        ))
    except KeyboardInterrupt:
        print("\n[simulator] Simulation cancelled by user.")


if __name__ == "__main__":
    main()
