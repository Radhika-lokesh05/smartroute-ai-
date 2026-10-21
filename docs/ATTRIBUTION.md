# Third-Party Attributions & Data Licenses

SmartRoute AI integrates open-source libraries, open geospatial data, and public APIs. We gratefully acknowledge the following data providers and open-source projects:

---

## 1. Map Data & Geospatial Services
- **OpenStreetMap**:
  - Map tiles, road geometries, and hospital points-of-interest are provided by [OpenStreetMap](https://www.openstreetmap.org) contributors.
  - **License**: Open Database License ([ODbL 1.0](https://opendatacommons.org/licenses/odbl/)).
  - Any user-facing map rendering displays attribution: `© OpenStreetMap contributors`.
- **OpenRouteService (HeiGIT)**:
  - Driving directions, routing polygons, and Pelias forward/reverse geocoding services are powered by [OpenRouteService](https://openrouteservice.org/) developed by the Heidelberg Institute for Geoinformation Technology (HeiGIT).
  - Terms of Service: Free research/developer tier terms apply.
- **Overpass API**:
  - Overpass API queries are utilized for discovering and extracting emergency healthcare facility nodes within the Bengaluru metropolitan bounding box.

---

## 2. Weather Intelligence
- **Open-Meteo**:
  - Live temperature, precipitation, and WMO weather codes are fetched from the [Open-Meteo Weather API](https://open-meteo.com/).
  - **License**: Free Weather API licensed under [Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).

---

## 3. Historical Traffic Dataset
- **Dataset Name**: Bengaluru Traffic Congestion Dataset
- **Source Link**: https://www.kaggle.com/datasets (or respective data repository)
- **License**: <!-- TODO: Fill in the specific license text (e.g. CC0, CC-BY-SA, Database Contents License) based on your exact dataset source -->

---

## 4. Notable Open-Source Libraries

### Backend
- **FastAPI**: MIT License (Sebastián Ramírez)
- **SQLAlchemy & GeoAlchemy2**: MIT License
- **Uvicorn**: BSD 3-Clause License
- **scikit-learn**: BSD 3-Clause License
- **Pydantic**: MIT License
- **asyncpg**: Apache License 2.0
- **python-jose**: MIT License
- **httpx**: BSD 3-Clause License

### Frontend
- **React & React-DOM**: MIT License (Meta Platforms, Inc.)
- **Leaflet & React-Leaflet**: BSD 2-Clause License / Hippocratic License
- **TanStack React Query**: MIT License
- **Lucide Icons**: ISC License
- **Tailwind CSS**: MIT License
