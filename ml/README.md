# SmartRoute AI - Machine Learning Service (`/ml`)

This directory houses the predictive models and intelligence pipeline for the SmartRoute AI ecosystem.

## Planned Capabilities
- **Traffic Congestion Prediction**: LightGBM regression model trained on historical traffic velocity, weather conditions, time-of-day, and incident patterns.
- **Incident Severity Classification**: Emergency triage model classifying reported road hazards and accident reports.
- **Dynamic Travel Time Estimation**: Real-time adjustment factor generator complementing OpenRouteService isochrones.

## Tooling
- Python 3.11+
- LightGBM, Scikit-learn, Pandas, NumPy
- Open-Meteo historical and forecast weather integrations
