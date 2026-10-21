# 5-Minute Live Demonstration Script: SmartRoute AI

This step-by-step presentation script is designed for live project reviews, video recordings, or evaluator walkthroughs. It demonstrates the complete end-to-end lifecycle in exactly 5 minutes.

---

## Preparation (Before Starting)
1. **Backend Server Running**:
   ```bash
   cd backend
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```
2. **Frontend Running**:
   ```bash
   cd frontend
   npm run dev
   ```
3. **Browser**: Open `http://localhost:5173` in Chrome / Edge.

---

## Demonstration Timeline (00:00 - 05:00)

### 00:00 - 01:00: Platform Overview & Civilian Navigation
1. **Navigate to App**: Open `http://localhost:5173`.
2. **Login**: Click "Sign In", click "Auto-fill" (or use `admin@smartroute.ai` / `adminpassword123`), and submit.
3. **Interactive Map**: Show Bengaluru metropolitan map with dark-mode styling and OpenStreetMap tiles.
4. **Calculate Route**:
   - Origin: Enter `MG Road, Bengaluru` (or click map).
   - Destination: Enter `Indiranagar, Bengaluru`.
   - Click "Find Routes".
   - **Showcase**: Multiple ranked alternative driving routes with distance, estimated travel time, and ML congestion factor.

### 01:00 - 02:00: Incident Reporting & Realtime Crowd Validation
1. **Report Incident**:
   - Click the "Report Incident" button.
   - Select Type: `Accident (Severe)`.
   - Coordinate: Click near the primary route corridor on Old Airport Road.
   - Note: `"Multi-vehicle collision blocking 2 lanes"`.
   - Submit Report.
2. **Realtime Broadcast**:
   - Show the marker appearing on the map in real time via WebSocket (`incident.created`).
   - Point out that it is in `pending` status with initial trust score.
3. **Crowd-Voting Validation**:
   - Vote to confirm the incident.
   - Notice the threshold count advancing (`confirmations: 2/3`).
   - When confirmed, note the transition to `validated` (`incident.validated` event).

### 02:00 - 03:00: Incident-Aware Dynamic Rerouting
1. **Recalculate Route**: Click "Find Routes" again along the same corridor.
2. **Dynamic Penalty & Avoidance**:
   - Observe how the engine detects the validated accident on the primary road.
   - The primary route now incurs a +600s delay penalty.
   - An avoidance polygon is computed around the accident.
   - The engine automatically promotes the clear alternative road as the `#1 Recommended Route`.

### 03:00 - 04:00: Emergency Ambulance Dispatch & Telemetry Simulator
1. **Trigger Dispatch**:
   - Open `/ambulance` or trigger emergency dispatch from the accident card.
   - Show the dispatch offer modal appearing for the ambulance unit.
   - Click "Accept Dispatch".
2. **Run Telemetry Simulator**:
   - In a terminal, run the telemetry script to simulate the ambulance en-route:
     ```bash
     python scripts/simulate_ambulance.py --lat 12.9716 --lng 77.5946 --distance 2000 --speed 45
     ```
3. **Live Telemetry & Proximity Warning**:
   - Show the ambulance icon moving smoothly in real time on the map (`ambulance.location` WebSocket feed).
   - In the civilian map view, observe the proximity alert warning civilians to yield right-of-way within 1.5 km of the approaching emergency vehicle.

### 04:00 - 05:00: Emergency Hospital Ranking & Admin Analytics
1. **Hospital Suggestions**:
   - Navigate to `/hospitals`.
   - Select Emergency Specialization: `Trauma & Critical Care`.
   - Point out that facilities are ranked not merely by geometric distance, but by real-time travel duration incorporating live traffic and road incidents.
2. **Admin Command Center**:
   - Navigate to `/admin`.
   - **Metrics Overview**: Show median and P90 validation times, dispatch acceptance rate, and SLA performance.
   - **Spatial Heatmap**: Show the PostGIS 250m snapped spatial grid clustering incident blackspots.
   - **Audit Trail**: Show the immutable audit log recording the dispatch and incident actions.
   - **Export CSV**: Click "Export CSV" and note privacy redaction (no user emails) and formula injection protection.
