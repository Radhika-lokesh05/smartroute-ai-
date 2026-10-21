"""
WebSocket Listener CLI Script for SmartRoute AI.
Connects to /ws with JWT auth token, subscribes to an area, and streams live incident events.

Usage:
    python -m scripts.ws_listen --token <JWT_TOKEN> --lat 12.9716 --lng 77.5946 --radius 5000
"""
import argparse
import asyncio
import json
import sys
import websockets


async def listen(url: str, token: str, lat: float, lng: float, radius: float) -> None:
    print(f"[ws_listen] Connecting to {url}...")
    try:
        async with websockets.connect(url) as ws:
            print("[ws_listen] Connected! Sending authentication token...")
            # Step 1: Authenticate without putting token in URL
            auth_payload = {"type": "auth", "token": token}
            await ws.send(json.dumps(auth_payload))

            auth_reply = await ws.recv()
            print(f"[ws_listen] Auth response: {auth_reply}")
            auth_data = json.loads(auth_reply)
            if auth_data.get("type") != "auth.success":
                print(f"[ws_listen] Authentication failed: {auth_reply}")
                return

            # Step 2: Subscribe to geographic area
            print(f"[ws_listen] Subscribing to area: lat={lat}, lng={lng}, radius={radius}m...")
            sub_payload = {
                "type": "subscribe",
                "lat": lat,
                "lng": lng,
                "radius_m": radius,
            }
            await ws.send(json.dumps(sub_payload))

            sub_reply = await ws.recv()
            print(f"[ws_listen] Subscription confirmed: {sub_reply}")
            print("-" * 60)
            print("[ws_listen] Listening for live incident updates (Press Ctrl+C to exit)...")
            print("-" * 60)

            # Step 3: Stream live events
            while True:
                msg = await ws.recv()
                try:
                    parsed = json.loads(msg)
                    formatted = json.dumps(parsed, indent=2)
                    print(f"\n[EVENT RECEIVED @ {parsed.get('timestamp', 'N/A')}]")
                    print(formatted)
                except Exception:
                    print(f"\n[RAW MESSAGE]: {msg}")

    except websockets.exceptions.ConnectionClosed as exc:
        print(f"\n[ws_listen] Connection closed by server: code={exc.code}, reason={exc.reason}")
    except Exception as exc:
        print(f"\n[ws_listen] Error: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="SmartRoute AI Realtime WebSocket Listener")
    parser.add_argument("--url", default="ws://127.0.0.1:8000/ws", help="WebSocket URL (default: ws://127.0.0.1:8000/ws)")
    parser.add_argument("--token", required=True, help="JWT access token for authentication")
    parser.add_argument("--lat", type=float, default=12.9716, help="Subscription center latitude (default: 12.9716 Bengaluru)")
    parser.add_argument("--lng", type=float, default=77.5946, help="Subscription center longitude (default: 77.5946 Bengaluru)")
    parser.add_argument("--radius", type=float, default=5000.0, help="Subscription radius in meters (default: 5000.0)")

    args = parser.parse_args()

    try:
        asyncio.run(listen(args.url, args.token, args.lat, args.lng, args.radius))
    except KeyboardInterrupt:
        print("\n[ws_listen] Exiting cleanly.")
        sys.exit(0)


if __name__ == "__main__":
    main()
