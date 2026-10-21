# Production Deployment Guide (Render Blueprint - Zero Docker)

This guide covers deploying SmartRoute AI to [Render](https://render.com) using Infrastructure-as-Code (`render.yaml`), configuring production environment variables, understanding platform limits, and running database migrations safely.

---

## 1. Hosting Architecture Overview
- **Deployment Style**: Zero Docker. Native Python 3.11 web service runtime and Node-based static site hosting.
- **Backend**: Render Python Web Service (`uvicorn app.main:app`).
- **Frontend**: Render Static Site (Vite Single Page Application with client-side routing).
- **Database**: Managed PostgreSQL with PostGIS extension (e.g. Neon Serverless Postgres or Supabase).

---

## 2. Production Environment Variables Reference

| Variable Name | Used In | Example / Format | Secret? | Description |
|---|---|---|---|---|
| `DATABASE_URL` | Backend | `postgresql+asyncpg://user:pass@ep-host.aws.neon.tech/neondb?ssl=require` | **YES** | Primary async PostgreSQL connection string. Must include PostGIS extension. |
| `JWT_SECRET` | Backend | `k9#mP2$xL9!vR8@wQ4^zT7*bN1&jY5(c` | **YES** | Cryptographic secret for signing JWTs. Must be >= 32 characters in production. |
| `ALLOWED_ORIGINS` | Backend | `https://smartroute.onrender.com,https://app.smartroute.ai` | NO | Comma-separated list or JSON array of authorized CORS origins. No wildcards in production. |
| `ENV` | Backend | `production` | NO | Execution mode (`development` or `production`). Triggers startup security verification. |
| `TRUSTED_PROXY_HOPS` | Backend | `1` | NO | Number of reverse proxy hops to trust for extracting client IP from `X-Forwarded-For`. |
| `ORS_API_KEY` | Backend | `5b3ce3597851110001cf6248...` | **YES** | OpenRouteService / HeiGIT API token for directions and Pelias geocoding. |
| `ORS_BASE_URL` | Backend | `https://api.heigit.org` | NO | Upstream base URL for OpenRouteService directions API. |
| `ORS_GEOCODE_BASE_URL`| Backend | `https://api.openrouteservice.org` | NO | Upstream base URL for Pelias geocoding engine. |
| `ADMIN_EMAIL` | Backend | `admin@smartroute.ai` | NO | Email address used for initial admin seeding script (`scripts/seed_admin.py`). |
| `ADMIN_PASSWORD` | Backend | `SecureAdminPass2026!` | **YES** | Password used only for initial admin seeding script. |
| `VITE_API_URL` | Frontend | `https://smartroute-backend.onrender.com` | NO | Public URL of the backend API service (without trailing slash). |
| `VITE_TILE_URL` | Frontend | `https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png` | NO | Leaflet tile layer URL template (supports custom Mapbox / Stadia URLs). |
| `VITE_TILE_ATTRIBUTION`| Frontend| `&copy; OpenStreetMap contributors` | NO | Tile layer copyright / attribution string. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Backend | `60` | NO | JWT lifespan before expiration (default 60 minutes). |
| `RATE_LIMIT_PER_MINUTE` | Backend | `60` | NO | Sliding window rate limit per user for routing and geocoding endpoints. |
| `HEATMAP_GRID_M` | Backend | `250.0` | NO | Grid cell snapping size in meters for PostGIS incident heatmap aggregation. |

---

## 3. How Migrations Run on Deploy
In `render.yaml`, the backend service defines:
```yaml
startCommand: cd backend && alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```
- **Idempotence**: Alembic evaluates `alembic_version` in the target PostgreSQL database. If migrations are already up to date, it exits within milliseconds and proceeds immediately to launch `uvicorn`.
- **Free-Tier Compatibility**: Render's `preDeployCommand` is only available on paid plans. Placing `alembic upgrade head` before `uvicorn` in `startCommand` ensures 100% reliable, automated database upgrades on **both Free and Paid** Render tiers without requiring Docker or manual intervention.
- **Fail-Safe**: If a database migration fails, the process exits non-zero, preventing the application from starting in an inconsistent state.

---

## 4. Honest Platform Limitations & Single-Process Caveats

### Render Free Tier Characteristics:
1. **Inactivity Sleep (Spin-Down)**:
   - Free web services automatically spin down after **15 minutes** of inactivity.
   - **Cold Start**: The first incoming HTTP request takes ~50-90 seconds to wake the instance.
   - **WebSocket Disconnection**: When an instance spins down, active WebSocket connections are terminated.
2. **Ephemeral File System**:
   - File system changes made during runtime are lost across restarts and redeployments. Machine learning model artifacts (`model.joblib`, `zones.json`) must be checked into git or downloaded during the build step.

### Single-Instance Process Memory Architecture:
All transient state in SmartRoute AI currently lives in **one Python OS process**:
- **WebSocket Connections**: Active client connections are tracked in `realtime_manager` in memory.
- **Rate Limiters**: Failed login counters and sliding-window request trackers reside in memory dictionaries.
- **Token Denylist**: Logged-out JWT IDs (`jti`) reside in `TOKEN_DENYLIST`.
- **Ambulance Live Coordinates**: High-frequency telemetry updates reside in `ambulance_tracker` and are flushed periodically to PostgreSQL.
- **Route Cache**: ORS routing responses are cached in process RAM.

### Scaling & High-Availability Path:
Because state is stored in-memory:
- **Single Instance Requirement**: The service must run as **exactly 1 instance** (`numInstances: 1`).
- **What Must Change to Scale Beyond 1 Instance**:
  1. **Redis**: Replace in-memory dictionaries with a centralized Redis instance (for WebSocket pub/sub broadcasting across worker nodes, shared token denylist, centralized rate limiting, and ambulance coordinates).
  2. **Celery / Arq**: Background sweeper loops (incident expiry and stale ambulance sweeps) should transition to a distributed task runner with leader election to avoid duplicate processing.

---

## 5. Render Research Summary (Confirmed vs Unconfirmed)

### Confirmed via Official Render Documentation:
- [x] **Web Service Blueprint**: `type: web`, `runtime: python`, `buildCommand`, and `startCommand` work seamlessly without Docker.
- [x] **Static Site Blueprint**: `runtime: static`, `staticPublishPath`, `routes` (`type: rewrite`), and custom HTTP `headers` (Content-Security-Policy, HSTS) are fully supported.
- [x] **Health Checks**: `healthCheckPath` on web services probes HTTP endpoints (we configured `/ready`).
- [x] **Secrets Handling**: `sync: false` properly marks environment variables to be supplied exclusively in the Render dashboard without committing secrets to git.
- [x] **WebSocket Support**: Render natively proxies WebSocket traffic over `wss://` (standard port 443 externally, mapped to `$PORT` internally).
- [x] **Reverse Proxy IP**: Render proxies requests through Cloudflare; `X-Forwarded-For` contains the client IP. `TRUSTED_PROXY_HOPS=1` correctly extracts the real client IP.

### Could Not Confirm / Unconfirmed:
- [ ] **Free Tier Bandwidth Soft vs Hard Cap**: Whether free static sites hard-throttle or temporarily suspend when exceeding 100 GB monthly bandwidth.
- [ ] **Exact WebSocket Idle Timeout at Render Edge**: Render recommends sending application-level heartbeats every 25-30 seconds to prevent edge proxy timeouts (implemented in `RealtimeClient.ts`).
