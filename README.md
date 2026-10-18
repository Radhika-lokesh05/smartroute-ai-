# SmartRoute AI

> Emergency-aware intelligent traffic routing system featuring real-time accident rerouting, ambulance green-corridor priority, and dynamic hospital emergency capacity telemetry.

---

## Monorepo Architecture

```
smartroute-ai/
├── backend/          # FastAPI async REST API & Neon PostgreSQL/PostGIS engine
│   ├── app/
│   │   ├── api/      # API route controllers (/health, etc.)
│   │   ├── core/     # Settings (pydantic-settings), database engine, security
│   │   ├── models/   # SQLAlchemy ORM models
│   │   ├── schemas/  # Pydantic request/response schemas
│   │   └── services/ # Routing and triage business logic
│   └── tests/        # Pytest test suite with async fixtures
├── frontend/         # Vite + React 18 + TypeScript + Tailwind CSS UI
│   ├── src/
│   │   ├── api/      # Axios HTTP client and API functions
│   │   ├── components/ # Reusable UI components
│   │   ├── hooks/    # React Query hooks
│   │   ├── pages/    # Route pages (Home telemetry dashboard)
│   │   └── types/    # TypeScript data definitions
├── ml/               # LightGBM congestion models and prediction pipelines
├── docs/             # Technical specifications and architecture guides
└── .gitignore        # Monorepo git ignore rules
```

---

## Prerequisites

- **Python**: Version `3.10` or higher (`python --version`)
- **Node.js**: Version `18.0` or higher (`node --version`)
- **npm**: Version `9.0` or higher (`npm --version`)
- **Note**: No Docker required. All services run natively on host via virtual environment and npm.

---

## Quick Start: Step-by-Step Commands

### 1. Backend Setup & Run

#### **Windows (PowerShell)**
```powershell
# Navigate to backend directory
cd backend

# Create Python virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1
# (If script execution policy is restricted, run: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass)

# Upgrade pip and install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt

# Create local environment file from example
Copy-Item .env.example .env

# Run automated tests
pytest

# Start FastAPI development server (runs at http://localhost:8000)
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

#### **Windows (Command Prompt / CMD)**
```cmd
cd backend
python -m venv venv
venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
pytest
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

#### **macOS & Linux (Bash / Zsh)**
```bash
# Navigate to backend directory
cd backend

# Create Python virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Create local environment file from example
cp .env.example .env

# Run automated tests
pytest

# Start FastAPI development server (runs at http://localhost:8000)
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

---

### 2. Frontend Setup & Run

#### **Windows (PowerShell or CMD)**
```powershell
# Navigate to frontend directory in a separate terminal
cd frontend

# Create local environment file from example
Copy-Item .env.example .env

# Install Node dependencies
npm install

# Start Vite development server (runs at http://localhost:5173)
npm run dev
```

#### **macOS & Linux (Bash / Zsh)**
```bash
# Navigate to frontend directory in a separate terminal
cd frontend

# Create local environment file from example
cp .env.example .env

# Install Node dependencies
npm install

# Start Vite development server (runs at http://localhost:5173)
npm run dev
```

---

## Verifying the Setup

1. **Backend Health Check**:
   - Open [http://localhost:8000/health](http://localhost:8000/health) in your browser.
   - You should see:
     ```json
     {
       "status": "ok",
       "service": "SmartRoute AI Backend",
       "database": "unreachable",
       "database_detail": "..."
     }
     ```
     *(Note: If a live Neon PostgreSQL database URL is configured in `backend/.env`, `"database"` will display `"connected"`. The endpoint never crashes when the database is unreachable or offline).*

2. **Interactive API Documentation (Swagger)**:
   - Visit [http://localhost:8000/docs](http://localhost:8000/docs) to explore the OpenAPI documentation.

3. **Frontend Dashboard**:
   - Open [http://localhost:5173](http://localhost:5173) in your browser.
   - When the backend is running, the dashboard displays **"Backend connected"** with an active telemetry badge.
   - If the backend is stopped, the card automatically transitions to **"Backend offline"** without unhandled exceptions.

4. **Running Automated Tests**:
   ```bash
   cd backend
   pytest -v
   ```

5. **Building Frontend for Production**:
   ```bash
   cd frontend
   npm run build
   ```

---

## Environment Variables Reference

### Backend (`backend/.env`)
| Variable | Description | Example Format |
| :--- | :--- | :--- |
| `DATABASE_URL` | Neon PostgreSQL asyncpg connection string (`?ssl=require`) | `postgresql+asyncpg://user:pass@ep-host.region.aws.neon.tech/neondb?ssl=require` |
| `ORS_API_KEY` | OpenRouteService API key for route calculations | `your_openrouteservice_key` |
| `JWT_SECRET` | Secret key for JWT signing & verification | `minimum_32_characters_secret_key` |
| `ALLOWED_ORIGINS`| Comma-separated CORS allowed origins | `http://localhost:5173,http://127.0.0.1:5173` |

### Frontend (`frontend/.env`)
| Variable | Description | Default |
| :--- | :--- | :--- |
| `VITE_API_URL` | Base URL of the FastAPI backend server | `http://localhost:8000` |
