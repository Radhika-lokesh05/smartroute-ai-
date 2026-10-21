export interface GeoJSONLineString {
  type: 'LineString';
  // Array of [longitude, latitude] coordinate pairs per GeoJSON specification
  coordinates: [number, number][];
}

export interface RouteStep {
  instruction: string;
  distance_m: number;
  duration_s: number;
  name: string;
  maneuver_type: string;
}

export interface IncidentOnRoute {
  id: string;
  type: string;
  status: string;
  lat: number;
  lng: number;
  distance_from_route_m: number;
}

export interface RouteSummary {
  incidents_considered: number;
  fastest_raw_route_index: number;
  recommended_route_index: number;
  rerouted: boolean;
}

export interface WeatherInfo {
  condition: string;
  precipitation_mm: number;
  visibility_m: number;
  temperature_c: number;
  source?: string;
  fetched_at?: string;
}

export interface RouteTrafficSummary {
  model_version: string;
  data_source: string;
  data_granularity: string;
  time_of_day_modelled: boolean;
  model_available: boolean;
  weather?: WeatherInfo | null;
}

export interface RouteItem {
  distance_m: number;
  duration_s: number;
  traffic_factor?: number;
  predicted_duration_s?: number;
  traffic_coverage?: number;
  estimated_delay_s: number;
  adjusted_duration_s: number;
  incidents_on_route: IncidentOnRoute[];
  avoids_incidents: boolean;
  rank: number;
  reason: string;
  geometry: GeoJSONLineString;
  steps: RouteStep[];
}

export interface RouteResponse {
  provider: string; // 'openrouteservice' or 'osrm-demo'
  warning?: string | null;
  summary?: RouteSummary | null;
  traffic?: RouteTrafficSummary | null;
  routes: RouteItem[];
}

export interface WayPoint {
  label: string;
  lat: number;
  lng: number;
}
