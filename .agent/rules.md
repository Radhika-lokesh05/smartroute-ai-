Project: SmartRoute AI - emergency-aware routing, accident alerts, ambulance priority, hospital suggestion.
Stack: React+TypeScript+Vite+Tailwind frontend; FastAPI async backend; PostgreSQL+PostGIS (Neon); OpenRouteService; Open-Meteo; LightGBM.
No Docker. Run everything with python venv and npm.
Rules: small modular files, type hints everywhere, no hardcoded URLs or secrets (use .env), tests for every backend feature, simulated data must always be labelled as simulated, update README after each step.