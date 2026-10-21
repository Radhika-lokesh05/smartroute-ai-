/**
 * Road incident types and WebSocket contract definitions.
 * Matches backend FastAPI schemas and WebSocket specifications.
 */

export type IncidentType = 'accident' | 'blockage' | 'hazard';

export type IncidentStatus = 'pending' | 'validated' | 'resolved' | 'expired';

export type VoteType = 'confirm' | 'reject';

export interface Incident {
  id: string;
  incident_type: IncidentType;
  type?: IncidentType;
  status: IncidentStatus;
  lat: number;
  lng: number;
  confirmations: number;
  rejections: number;
  trust_score: number;
  created_at: string;
  expires_at: string;
  validated_at?: string | null;
  resolved_at?: string | null;
  seconds_remaining: number;
  note?: string | null;
  user_voted: boolean;
  user_vote?: VoteType | null;
  distance_m?: number | null;
}

export type IncidentPublic = Incident;

export interface IncidentListResponse {
  total: number;
  incidents: Incident[];
}

export interface IncidentCreatePayload {
  lat: number;
  lng: number;
  type: IncidentType;
  note?: string;
}

export interface IncidentVotePayload {
  vote: VoteType;
  voter_lat: number;
  voter_lng: number;
}

export interface IncidentBroadcastData {
  id: string;
  incident_type: IncidentType;
  status: IncidentStatus;
  lat: number;
  lng: number;
  confirmations: number;
  rejections: number;
  trust_score: number;
  created_at: string;
  expires_at: string;
  validated_at?: string | null;
  resolved_at?: string | null;
  seconds_remaining: number;
  note?: string | null;
}

// ---------------------------------------------------------------------------
// WebSocket Message Contract (v: 1)
// ---------------------------------------------------------------------------

export type WsEventType =
  | 'incident.created'
  | 'incident.updated'
  | 'incident.validated'
  | 'incident.resolved'
  | 'incident.expired';

import {
  WsAmbulanceLocationClientMessage,
  WsAmbulanceNearbyMessage,
  WsAmbulanceClearMessage,
  WsDispatchOfferMessage,
  WsDispatchUpdatedMessage,
  WsDispatchCancelledMessage,
  WsHospitalPrealertMessage,
} from './dispatch';

// Client to Server Messages
export interface WsAuthMessage {
  type: 'auth';
  token: string;
}

export interface WsSubscribeMessage {
  type: 'subscribe';
  lat: number;
  lng: number;
  radius_m: number;
}

export interface WsPingMessage {
  type: 'ping';
}

export type WsClientMessage =
  | WsAuthMessage
  | WsSubscribeMessage
  | WsPingMessage
  | WsAmbulanceLocationClientMessage;

// Server to Client Messages
export interface WsAuthSuccessMessage {
  v: 1;
  type: 'auth.success';
  user_id: string;
}

export interface WsSubscribeSuccessMessage {
  v: 1;
  type: 'subscribe.success';
  lat: number;
  lng: number;
  radius_m: number;
}

export interface WsPongMessage {
  v: 1;
  type: 'pong';
}

export interface WsErrorMessage {
  v: 1;
  type: 'error';
  message: string;
}

export interface WsIncidentEventMessage {
  v: 1;
  type: WsEventType;
  timestamp: string;
  data: IncidentBroadcastData;
  route_impact?: boolean;
}


export type WsServerMessage =
  | WsAuthSuccessMessage
  | WsSubscribeSuccessMessage
  | WsPongMessage
  | WsErrorMessage
  | WsIncidentEventMessage
  | WsAmbulanceNearbyMessage
  | WsAmbulanceClearMessage
  | WsDispatchOfferMessage
  | WsDispatchUpdatedMessage
  | WsDispatchCancelledMessage
  | WsHospitalPrealertMessage;

export type RealtimeConnectionStatus = 'connecting' | 'live' | 'connected' | 'reconnecting' | 'offline';
