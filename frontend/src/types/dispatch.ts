/**
 * Emergency ambulance dispatching, live telemetry, and proximity warning types.
 * Matches backend FastAPI schemas and WebSocket specifications.
 */

export type DispatchStatus =
  | 'offered'
  | 'accepted'
  | 'en_route_to_scene'
  | 'at_scene'
  | 'to_hospital'
  | 'completed'
  | 'declined'
  | 'expired'
  | 'cancelled';

export type AmbulanceStatus = 'available' | 'offline' | 'busy';

export interface AmbulanceRecord {
  id: string;
  user_id: string;
  plate_number: string;
  status: AmbulanceStatus;
  is_verified: boolean;
  last_seen_at?: string | null;
}

export interface DispatchResponse {
  id: string;
  incident_id: string;
  ambulance_id: string;
  hospital_id?: string | null;
  status: DispatchStatus;
  offered_at: string;
  accepted_at?: string | null;
  arrived_at?: string | null;
  picked_up_at?: string | null;
  completed_at?: string | null;
  eta_to_scene_s: number;
  eta_to_hospital_s: number;
  emergency_type: string;
  offer_number: number;
}

export interface DispatchOfferData {
  dispatch_id: string;
  incident_id: string;
  emergency_type: string;
  incident_lat: number;
  incident_lng: number;
  eta_to_scene_s: number;
  expires_in_s: number;
}

export interface DispatchUpdateData {
  dispatch_id: string;
  status: DispatchStatus;
  hospital_id?: string | null;
  timestamp: string;
}

// ---------------------------------------------------------------------------
// Realtime WebSocket Extensions (v: 1)
// ---------------------------------------------------------------------------

export interface WsAmbulanceLocationClientMessage {
  type: 'ambulance.location';
  lat: number;
  lng: number;
  heading: number;
  speed: number;
}

export interface WsAmbulanceNearbyMessage {
  v: 1;
  type: 'ambulance.nearby';
  distance_m: number;
  bearing_deg: number;
  approaching: boolean;
  eta_s?: number;
  expires_in_s: number;
}

export interface WsAmbulanceClearMessage {
  v: 1;
  type: 'ambulance.clear';
}

export interface WsDispatchOfferMessage {
  v: 1;
  type: 'dispatch.offer' | 'dispatch.offered';
  data: DispatchOfferData;
}

export interface WsDispatchUpdatedMessage {
  v: 1;
  type: 'dispatch.updated';
  data: DispatchUpdateData;
}

export interface WsDispatchCancelledMessage {
  v: 1;
  type: 'dispatch.cancelled';
  data?: {
    dispatch_id: string;
    reason?: string;
  };
}

export interface WsHospitalPrealertMessage {
  v: 1;
  type: 'hospital.prealert';
  data: {
    dispatch_id?: string;
    hospital_id?: string;
    eta_s?: number;
    emergency_type?: string;
  };
}

export type { WsServerMessage, WsClientMessage } from './incident';

