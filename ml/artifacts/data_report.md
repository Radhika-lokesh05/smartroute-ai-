# Bengaluru Traffic Dataset Inspection Report

- **Dataset File**: `Banglore_traffic_Dataset.csv`
- **Location**: `ml/data/Banglore_traffic_Dataset.csv`
- **Format**: CSV
- **Total Rows**: 8,937 observations (8,938 lines including header)
- **Total Columns**: 16 columns
- **Date Range**: `2022-01-01` to `2024-08-09` (2 years, 7 months, 9 days)
- **Granularity**: **Daily** (No time-of-day / hourly column exists; one aggregated observation per road/area per date)

---

## 1. Column Inventory & Missing Values

| Column Name | Inferred Type | Missing Count | Missing % | Sample Value | Description & Assessment |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `Date` | Date (`YYYY-MM-DD`) | 0 | 0.0% | `2022-01-01` | Daily date timestamp |
| `Area Name` | Categorical (String) | 0 | 0.0% | `Indiranagar` | Primary urban zone / locality in Bengaluru |
| `Road/Intersection Name` | Categorical (String) | 0 | 0.0% | `100 Feet Road` | Specific corridor or intersection within the area |
| `Traffic Volume` | Numeric (Integer) | 0 | 0.0% | `50590` | Measured vehicle count (Leaked at test time) |
| `Average Speed` | Numeric (Float) | 0 | 0.0% | `50.23` | Average observed speed in km/h (Leaked at test time) |
| `Travel Time Index` | Numeric (Float) | 0 | 0.0% | `1.5` | Ratio of actual travel time to free-flow travel time (Candidate Target) |
| `Congestion Level` | Numeric (Float) | 0 | 0.0% | `100.0` | Congestion percentage index (0.0 to 100.0) |
| `Road Capacity Utilization` | Numeric (Float) | 0 | 0.0% | `100.0` | Capacity saturation percentage (0.0 to 100.0) |
| `Incident Reports` | Numeric (Integer) | 0 | 0.0% | `0` | Number of incident reports on that date |
| `Environmental Impact` | Numeric (Float) | 0 | 0.0% | `151.18` | Emissions/pollution index |
| `Public Transport Usage` | Numeric (Float) | 0 | 0.0% | `70.63` | Public transit share |
| `Traffic Signal Compliance` | Numeric (Float) | 0 | 0.0% | `84.04` | Compliance percentage |
| `Parking Usage` | Numeric (Float) | 0 | 0.0% | `85.40` | Parking occupancy rate |
| `Pedestrian and Cyclist Count` | Numeric (Integer) | 0 | 0.0% | `111` | Non-motorized road user count |
| `Weather Conditions` | Categorical (String) | 0 | 0.0% | `Clear` | Weather category observed on that date |
| `Roadwork and Construction Activity` | Categorical (String) | 0 | 0.0% | `No` | Roadwork indicator (`Yes` / `No`) |

**Missing Value Assessment**: The dataset is complete with 0 missing values across all 16 columns.

---

## 2. Temporal Coverage & Granularity

- **Start Date**: `2022-01-01`
- **End Date**: `2024-08-09`
- **Unique Dates**: 952 distinct dates
- **Time-of-Day Column**: **None**. All observations are stamped with a daily date (`YYYY-MM-DD`). There are no hourly or sub-daily timestamps.
- **Granularity Finding**: Daily granularity. As required by the specification, when `time_of_day_modelled = false`, departure time in routing will influence day-of-week, month, weekend, public holiday, and forecasted weather, but cannot model intra-day rush-hour peaks without temporal distortion.

---

## 3. Geographical Entities (Areas & Roads)

The dataset covers **8 distinct major areas/zones** in Bengaluru across **16 roads/intersections**:

### Distinct Areas (8):
| Area Name | Observations | Share % | Geographic Role |
| :--- | :--- | :--- | :--- |
| `Indiranagar` | ~1,270 | 14.2% | East-Central commercial & residential hub |
| `Koramangala` | ~1,260 | 14.1% | South-East tech, retail & residential hub |
| `M.G. Road` | ~1,250 | 14.0% | Central Business District (CBD) |
| `Hebbal` | ~1,240 | 13.9% | North Bengaluru gateway & airport corridor |
| `Yeshwanthpur` | ~1,220 | 13.7% | North-West transit & industrial junction |
| `Jayanagar` | ~1,200 | 13.4% | South Bengaluru traditional residential zone |
| `Whitefield` | ~1,000 | 11.2% | Major East IT corridor & tech parks |
| `Electronic City` | ~500 | 5.6% | Major South IT cluster & elevated highway zone |

### Key Roads / Intersections (16):
- `100 Feet Road` (Indiranagar)
- `CMH Road` (Indiranagar)
- `Marathahalli Bridge` (Whitefield)
- `ITPL Main Road` (Whitefield)
- `Sony World Junction` (Koramangala)
- `Sarjapur Road` (Koramangala)
- `Trinity Circle` (M.G. Road)
- `Anil Kumble Circle` (M.G. Road)
- `Jayanagar 4th Block` (Jayanagar)
- `South End Circle` (Jayanagar)
- `Hebbal Flyover` (Hebbal)
- `Ballari Road` (Hebbal)
- `Yeshwanthpur Circle` (Yeshwanthpur)
- `Tumkur Road` (Yeshwanthpur)
- `Hosur Road` (Electronic City)
- `Silk Board Junction` (Electronic City)

---

## 4. Weather Conditions

The `Weather Conditions` column has **5 distinct categories**:

| Weather Condition | Observation Count | Share % | Mapping to Open-Meteo |
| :--- | :--- | :--- | :--- |
| `Clear` | ~4,820 | 53.9% | WMO codes 0 (Clear sky), 1 (Mainly clear) |
| `Overcast` | ~2,110 | 23.6% | WMO codes 2 (Partly cloudy), 3 (Overcast) |
| `Fog` | ~980 | 11.0% | WMO codes 45 (Fog), 48 (Depositing rime fog) |
| `Rain` | ~680 | 7.6% | WMO codes 51-67, 80-82 (Drizzle, Rain, Showers) |
| `Windy` | ~347 | 3.9% | High wind conditions / convective gusts |

---

## 5. Traffic & Congestion Metrics Distribution

| Metric Column | Min | Mean | Max | Std Dev | Interpretation |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `Average Speed` (km/h) | 20.00 | 39.85 | 66.42 | 11.20 | Ranging from severe crawl (20 km/h) to moderate free flow (66 km/h) |
| `Travel Time Index` | **1.00** | **1.38** | **1.50** | **0.17** | **Ratio of actual travel time to free flow ($\ge 1.0$)**. Highly clustered at ceiling 1.5 during congestion |
| `Congestion Level` (%) | 15.00 | 78.40 | 100.00 | 25.10 | Percentage index scaling to 100% saturation |
| `Road Capacity Utilization` (%)| 20.00 | 88.50 | 100.00 | 18.30 | Percentage of road capacity utilized |
| `Incident Reports` | 0 | 1.48 | 5 | 1.25 | Daily counts of incidents on the road |

---

## 6. Proposed ML Pipeline Strategy & Selections

### 1. TARGET Column Selection: `Travel Time Index`
- The `Travel Time Index` directly represents the prompt's required `congestion_factor`:
  $$\text{congestion\_factor} = \frac{\text{Trip Travel Time}}{\text{Free Flow Travel Time}} \ge 1.0$$
- In this dataset, `Travel Time Index` is bounded within $[1.00, 1.50]$.
- A value of `1.00` indicates uncongested free-flow conditions (trip takes $1.0\times$ normal duration).
- A value of `1.50` indicates maximum congestion in the dataset (trip takes $1.5\times$ normal duration, a 50% delay factor).
- **Target suitability**: Direct, robust, exactly fits the domain definition, and requires no synthetic derivation.
- Clipped range: $[1.00, 1.50]$ (0 rows clipped outside this natural boundary).

### 2. AREA Column Selection: `Area Name`
- Contains the 8 major geographic zones of Bengaluru (`Indiranagar`, `Whitefield`, `Koramangala`, `M.G. Road`, `Jayanagar`, `Hebbal`, `Yeshwanthpur`, `Electronic City`).
- Will be mapped to approximate geographic zone coordinates in `ml/zones.json`.

### 3. DATE Column Selection: `Date`
- Parsed to extract temporal features available at prediction time: `weekday`, `is_weekend`, `month`, and `is_holiday` (Indian public holidays via `holidays.country_holidays('IN', subdiv='KA')`).
- Year is strictly excluded to prevent temporal overfitting.

### 4. WEATHER Column Selection: `Weather Conditions`
- Contains 5 clean categories: `Clear`, `Overcast`, `Fog`, `Rain`, `Windy`.
- Will be mapped from Open-Meteo live weather codes via `ml/weather_mapping.yaml`.

### 5. Leakage Prevention (Excluded Features):
The following columns are strictly excluded from feature inputs as they are concurrent measurements not available when planning future routes:
- `Traffic Volume`
- `Average Speed`
- `Congestion Level`
- `Road Capacity Utilization`
- `Incident Reports`
- `Environmental Impact`
- `Public Transport Usage`
- `Traffic Signal Compliance`
- `Parking Usage`
- `Pedestrian and Cyclist Count`
- `Roadwork and Construction Activity`
