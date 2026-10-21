/**
 * Hospital emergency types and response schemas.
 * Matches backend FastAPI definitions in app/schemas/hospital.py.
 */

export type EmergencyType =
  | 'general'
  | 'trauma'
  | 'cardiac'
  | 'burns'
  | 'maternity'
  | 'pediatric';

export interface HospitalNearbyItem {
  id: string;
  name: string;
  lat: number;
  lng: number;
  phone?: string | null;
  address?: string | null;
  eta_s: number;
  distance_m: number;
  matches_type: boolean;
  simulated_beds: number;
  beds_simulated: boolean; // Always true, never presented as live
  eta_estimated: boolean;
  route_geometry?: {
    type: 'LineString';
    coordinates: [number, number][]; // [lng, lat] GeoJSON format
  } | null;
}

export interface HospitalNearbyResponse {
  emergency_number: string;
  disclaimer: string;
  hospitals: HospitalNearbyItem[];
}
