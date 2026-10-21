# SmartRoute AI

> **Emergency-Aware Intelligent Traffic Routing, Incident Prioritization & Telemetry Platform**

SmartRoute AI is a full-stack, zero-Docker geospatial intelligence system designed for urban traffic navigation and emergency response. It combines OpenRouteService routing corridors, crowd-sourced incident validation with PostGIS spatial fencing, machine-learning traffic congestion prediction, live Open-Meteo weather normalization, real-time WebSocket telemetry, and emergency healthcare facility ranking.

---

## Architecture Overview

```mermaid
flowchart TD
    subgraph ClientLayer ["Client Layer (React 18 + Vite + Leaflet)"]
        CIV["Civilian Map & Rerouting UI"]
        AMB["Ambulance Operator Dashboard"]
        ADM["Admin Analytics & Heatmap"]
        RC["RealtimeClient (Auto-Reconnect wss://)"]
    end

    subgraph EdgeLayer ["Hosting & Security Edge (Render Cloud)"]
        CSP["Content-Security-Policy & Headers"]
        PROXY["Cloudflare Reverse Proxy (TRUSTED_PROXY_HOPS=1)"]
        RL["Client IP Rate Limiters (Login / Register / API)"]
    end

    subgraph BackendLayer ["Application Core (FastAPI Python 3.11 - Zero Docker)"]
        ROUTER["API Gateway & Auth (JWT + In-Memory Denylist)"]
        INC_SVC["Incident Lifecycle & Spatial Deduplication Engine"]
        ROUTE_SVC["Incident-Aware Routing & Avoidance Polygons"]
        DISP_SVC["Ambulance Tracking & Proximity Warning"]
        HOSP_SVC["Hospital Ranking & Delay Estimation"]
        RED_LOG["Redacting Logger (Filter Passwords/Tokens/URLs)"]
    end

    subgraph UpstreamLayer ["External Geospatial & Telemetry Services"]
        ORS["OpenRouteService / HeiGIT (Driving Directions & Pelias)"]
        METEO["Open-Meteo (Live Weather Telemetry)"]
        OSM["OpenStreetMap & Overpass API (Roads & Facilities)"]
    end

    subgraph DataLayer ["Data & Storage Layer"]
        POSTGIS[("PostgreSQL 15 + PostGIS (Neon Serverless)")]
        ML_MODEL["Scikit-Learn ML Model (Random Forest Artifact)"]
    end

    CIV <--> PROXY
    AMB <--> PROXY
    ADM <--> PROXY
    PROXY --> CSP --> RL --> ROUTER

    ROUTER <--> INC_SVC
    ROUTER <--> ROUTE_SVC
    ROUTER <--> DISP_SVC
    ROUTER <--> HOSP_SVC

    INC_SVC <--> POSTGIS
    DISP_SVC <--> POSTGIS
    ROUTE_SVC <--> ORS
    ROUTE_SVC <--> ML_MODEL
    ROUTE_SVC <--> METEO
    HOSP_SVC <--> OSM

    RED_LOG -.-> ROUTER
```

---

## Real vs. Simulated Capabilities Matrix

To maintain rigorous academic and engineering honesty, SmartRoute AI distinguishes verified technical implementations from simulated heuristics:

| Feature Area | What is REAL | What is SIMULATED / ESTIMATED |
|---|---|---|
| **Road Incidents** | PostGIS spatial deduplication (100m), physical proximity voting (1,000m), lifecycle state machine (pending → validated / expired / resolved), and geo-filtered WebSockets. | N/A (Crowd voting and spatial deduplication are 100% computed against database coordinates). |
| **Route Computation** | OpenRouteService driving geometry, alternative path analysis, dynamic avoid-polygon clipping, and turn-by-turn steps. | Incident delay penalties (+600s for accident, +900s for road blockage) are empirical heuristics applied to road corridors. |
| **Traffic Congestion** | Random Forest model trained on historical Bengaluru metropolitan congestion data predicting traffic factors from hour, day, weather, and zone centroids. | Real-time CCTV vision and physical road loop sensors are simulated by the ML inference model. |
| **Weather Telemetry** | Live temperature and precipitation fetched from Open-Meteo API with WMO weather condition code normalization. | Extreme storm scenarios can be overridden via synthetic test parameters. |
| **Hospitals** | Emergency healthcare facilities and amenities extracted from OpenStreetMap using Overpass QL and ranked by real-time travel duration. | Hospital bed availability, ICU occupancy, and ER intake queues are estimated models for demonstration. |
| **Ambulance Dispatches** | State machine (offer → accept/decline → scene → hospital), spatial candidate radius matching, and civilian proximity yielding alerts (<1.5 km). | Real-world municipal 108/911 emergency fleet hardware is simulated via `simulate_ambulance.py` for testing. |

---

## Production Environment Variables Reference

| Variable | Used In | Example / Format | Secret? | Description |
|---|---|---|---|---|
| `DATABASE_URL` | Backend | `postgresql+asyncpg://user:pass@host/db?ssl=require` | **YES** | Async PostgreSQL connection string with PostGIS. |
| `JWT_SECRET` | Backend | `k9#mP2$xL9!vR8@wQ4^zT7*bN1&jY5(c` | **YES** | Secret for signing JWTs (must be >= 32 characters in production). |
| `ALLOWED_ORIGINS` | Backend | `https://smartroute.onrender.com,https://app.domain.com` | NO | Comma-separated list of allowed CORS origins. |
| `ENV` | Backend | `production` or `development` | NO | Execution mode (enforces security validation in production). |
| `TRUSTED_PROXY_HOPS` | Backend | `1` | NO | Number of reverse proxy hops to trust for extracting client IP. |
| `ORS_API_KEY` | Backend | `5b3ce3597851110001cf...` | **YES** | OpenRouteService API key for directions and Pelias geocoding. |
| `ORS_BASE_URL` | Backend | `https://api.heigit.org` | NO | Upstream base URL for OpenRouteService directions. |
| `ORS_GEOCODE_BASE_URL`| Backend | `https://api.openrouteservice.org` | NO | Upstream base URL for Pelias geocoding service. |
| `ADMIN_EMAIL` | Backend | `admin@smartroute.ai` | NO | Admin account email for initial database seeding. |
| `ADMIN_PASSWORD` | Backend | `SecureAdmin2026!` | **YES** | Admin password for initial database seeding. |
| `VITE_API_URL` | Frontend | `https://smartroute-backend.onrender.com` | NO | REST API base URL for client application. |
| `VITE_TILE_URL` | Frontend | `https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png` | NO | Leaflet tile layer URL template. |
| `VITE_TILE_ATTRIBUTION`| Frontend| `&copy; OpenStreetMap contributors` | NO | Map tile layer attribution text. |

> [!IMPORTANT]
> **OpenStreetMap Public Tile Server Usage Note**:
> The default map tile URL (`tile.openstreetmap.org`) is operated by the OpenStreetMap Foundation using donated resources and is strictly intended for limited testing. It is **not meant for heavy production use**. For production deployments, update `VITE_TILE_URL` to point to a commercial provider (Mapbox, Stadia Maps, Jawg) or a self-hosted tile cache.

---

## Windows Setup & Local Run Guide (No Docker)

### Prerequisites
- **Python**: Version `3.11` (`python --version`)
- **Node.js**: Version `20.x` or `18.x` (`node --version`)
- **PostgreSQL**: Neon Serverless PostgreSQL or local PostgreSQL with PostGIS extension.

---

### Step 1: Backend Setup (PowerShell)

```powershell
# 1. Navigate to backend directory
cd backend

# 2. Create virtual environment
python -m venv venv

# 3. Activate virtual environment
.\venv\Scripts\Activate.ps1

# 4. Install production & dev dependencies
pip install -r requirements-dev.txt

# 5. Configure environment file (.env)
Copy-Item .env.example .env
# Edit .env with your DATABASE_URL, JWT_SECRET (>= 32 chars), and ORS_API_KEY

# 6. Apply database migrations
alembic upgrade head

# 7. Seed initial administrator account
python scripts/seed_admin.py

# 8. Start backend server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Verify backend is healthy:
- Liveness check: `http://127.0.0.1:8000/health`
- Readiness check: `http://127.0.0.1:8000/ready`
- Interactive API Docs (dev only): `http://127.0.0.1:8000/docs`

---

### Step 2: Frontend Setup (PowerShell)

Open a second terminal window:

```powershell
# 1. Navigate to frontend directory
cd frontend

# 2. Install dependencies
npm ci

# 3. Run type check and lint
npm run lint

# 4. Launch Vite development server
npm run dev
```

Open `http://localhost:5173` in your browser. Default Admin Login: `admin@smartroute.ai` / `adminpassword123`.

---

## Running the Automated Test Suites

### 1. Backend Tests with Coverage
```powershell
cd backend
pytest --cov=app/services --cov=app/api --cov-report=term-missing tests/
```

### 2. Machine Learning Tests
```powershell
pytest ml/tests/
```

### 3. Frontend Unit Tests & Secret Scan
```powershell
cd frontend
npm run test
npm run build
node ../scripts/check_bundle_secrets.mjs
```

### 4. Live Server End-to-End Smoke Test
Run against a running backend server to verify liveness, readiness, authentication, geocoding, incident reporting, voting, hospital ranking, and logout:
```powershell
python scripts/e2e_smoke.py --base-url http://127.0.0.1:8000
```

---

## Running the Simulators

### 1. Ambulance Movement & Telemetry Simulator
Simulates a live ambulance traveling along a road corridor, broadcasting real-time GPS telemetry over WebSockets to trigger civilian proximity alerts:
```powershell
python scripts/simulate_ambulance.py --lat 12.9716 --lng 77.5946 --distance 2000 --speed 45
```

### 2. Multi-Incident Scenario Simulator
Generates synthetic traffic accidents and hazards across Bengaluru metropolitan zones to test crowd-voting convergence, automatic rerouting, and admin heatmaps:
```powershell
python scripts/run_scenarios.py --incidents 8 --votes 25
```

To clean up simulated test records afterwards:
```powershell
python scripts/cleanup_simulated.py
```

---

## User Interface Screenshots

| Civilian Dynamic Routing | Admin Incident Density Heatmap |
|---|---|
| ![Civilian Routing](docs/screenshots/civilian_routing.png) | ![Admin Heatmap](docs/screenshots/admin_heatmap.png) |

| Emergency Dispatch Management | Ambulance Telemetry HUD |
|---|---|
| ![Dispatch Console](docs/screenshots/dispatch_console.png) | ![Ambulance HUD](docs/screenshots/ambulance_hud.png) |

*(Screenshots can be captured during demonstration runs and placed into `docs/screenshots/`)*

---

## Limitations and Honest Claims

1. **Single-Process In-Memory State**:
   - In the current reference implementation, transient state (active WebSockets, sliding-window rate limiters, token denylist, and live vehicle coordinates) lives in **one Python OS process memory**.
   - The application must run as a single instance (`numInstances: 1`).
   - To scale horizontally across multiple instances or regions, in-memory state and WebSockets must be migrated to a centralized Redis cluster.
2. **Hosting Platform Sleeping (Render Free Tier)**:
   - Free-tier web services automatically spin down after 15 minutes of inactivity. The first incoming request incurs a ~50-90s cold start delay, and active WebSocket connections are terminated during sleep. The frontend `RealtimeClient` incorporates automatic exponential backoff reconnection to recover when the backend resumes.
3. **Emergency Numbers**:
   - The platform provides routing and situational awareness; emergency contacts reference standard dispatch numbers (112 in India). It does not replace municipal 911/108 public safety answering points.

---

## License & Third-Party Credits
- **Project License**: See [LICENSE](LICENSE) (TODO: Choose project license).
- **Attributions**: Map data © [OpenStreetMap](https://www.openstreetmap.org) contributors (ODbL), routing by [OpenRouteService](https://openrouteservice.org) (HeiGIT), weather by [Open-Meteo](https://open-meteo.com) (CC BY 4.0). Full attributions in [docs/ATTRIBUTION.md](docs/ATTRIBUTION.md).
