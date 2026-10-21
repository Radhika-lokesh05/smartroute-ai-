import { Incident, IncidentBroadcastData, WsEventType } from '@/types/incident';
import { calculateDistanceM } from '@/utils/coordinates';

/**
 * Idempotently merges a realtime WebSocket incident broadcast into the local list of incidents.
 * - Removes resolved or expired incidents from active view.
 * - Updates or adds created, updated, or validated incidents.
 * - Preserves local user voting state (user_voted, user_vote).
 * - Recomputes distance and keeps incidents sorted by distance.
 * - Rejects stale updates (if event has older confirmations/trust score on existing incident).
 */
export function mergeIncidentIntoCache(
  currentIncidents: Incident[],
  eventType: WsEventType,
  data: IncidentBroadcastData,
  userLocation?: { lat: number; lng: number } | null
): Incident[] {
  // 1. If resolved or expired, remove from active list
  if (eventType === 'incident.resolved' || eventType === 'incident.expired' || data.status === 'resolved' || data.status === 'expired') {
    return currentIncidents.filter((inc) => inc.id !== data.id);
  }

  // Calculate distance if user location is known
  let distanceM: number | null = null;
  if (userLocation) {
    distanceM = calculateDistanceM(userLocation.lat, userLocation.lng, data.lat, data.lng);
  }

  const existingIndex = currentIncidents.findIndex((inc) => inc.id === data.id);

  if (existingIndex >= 0) {
    const existing = currentIncidents[existingIndex];

    // Ignore older or out-of-order updates
    // If the existing record has strictly more confirmations, or higher trust score and status is already validated
    if (
      existing.confirmations > data.confirmations ||
      (existing.status === 'validated' && data.status === 'pending')
    ) {
      return currentIncidents;
    }

    const updatedIncident: Incident = {
      ...existing,
      ...data,
      // Preserve local client voting interaction state
      user_voted: existing.user_voted,
      user_vote: existing.user_vote,
      distance_m: distanceM ?? existing.distance_m,
    };

    const nextList = [...currentIncidents];
    nextList[existingIndex] = updatedIncident;
    return sortIncidentsByDistance(nextList);
  }

  // New incident
  const newIncident: Incident = {
    ...data,
    user_voted: false,
    user_vote: null,
    distance_m: distanceM,
  };

  return sortIncidentsByDistance([...currentIncidents, newIncident]);
}

/**
 * Sorts incidents by distance (nearest first). If distance is missing, sorts by newest created.
 */
export function sortIncidentsByDistance(incidents: Incident[]): Incident[] {
  return [...incidents].sort((a, b) => {
    if (a.distance_m != null && b.distance_m != null) {
      return a.distance_m - b.distance_m;
    }
    if (a.distance_m != null) return -1;
    if (b.distance_m != null) return 1;
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
  });
}
