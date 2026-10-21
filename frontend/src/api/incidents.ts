import { apiClient } from './client';
import axios from 'axios';
import {
  Incident,
  IncidentCreatePayload,
  IncidentListResponse,
  IncidentVotePayload,
} from '@/types/incident';

/**
 * Report a new incident or merge into an existing active incident within deduplication radius.
 * If merged, the server registers the submission as an additional confirmation vote.
 */
export async function reportIncident(
  payload: IncidentCreatePayload
): Promise<{ incident: Incident; wasMerged: boolean }> {
  const response = await apiClient.post<Incident>('/api/incidents', payload);
  const incident = response.data;
  // A newly created incident starts with confirmations = 1.
  // If confirmations > 1, the backend merged this into an existing report.
  const wasMerged = incident.confirmations > 1;
  return { incident, wasMerged };
}

/**
 * Vote (confirm or reject) on an active incident.
 * Voter must be located within 1,000 meters of the incident location.
 */
export async function voteIncident(
  incidentId: string,
  payload: IncidentVotePayload
): Promise<Incident> {
  const response = await apiClient.post<Incident>(`/api/incidents/${incidentId}/vote`, payload);
  return response.data;
}

/**
 * Resolve an active incident.
 * Allowed only for the original reporter, verified ambulance operators, or administrators.
 */
export async function resolveIncident(incidentId: string): Promise<Incident> {
  const response = await apiClient.post<Incident>(`/api/incidents/${incidentId}/resolve`);
  return response.data;
}

/**
 * Fetch active, unexpired incidents within radius_m of the given location.
 */
export async function getNearbyIncidents(
  lat: number,
  lng: number,
  radius_m = 5000
): Promise<Incident[]> {
  const response = await apiClient.get<IncidentListResponse>('/api/incidents/nearby', {
    params: {
      lat,
      lng,
      radius_m,
    },
  });
  return response.data.incidents || [];
}

/**
 * Fetch a single incident by ID.
 */
export async function getIncidentById(incidentId: string): Promise<Incident> {
  const response = await apiClient.get<Incident>(`/api/incidents/${incidentId}`);
  return response.data;
}

/**
 * Maps server HTTP error responses into clean, user-friendly feedback strings.
 */
export function mapIncidentError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const status = error.response?.status;
    const detail = error.response?.data?.detail;
    const detailStr = typeof detail === 'string' ? detail : '';

    if (status === 409) {
      if (detailStr.toLowerCase().includes('already reported')) {
        return 'You have already reported an active incident at this location.';
      }
      return 'You have already voted on this incident.';
    }

    if (status === 400 || status === 422) {
      if (detailStr.toLowerCase().includes('radius') || detailStr.toLowerCase().includes('1000m')) {
        return 'You must be within 1 km of the incident to verify or vote.';
      }
      return detailStr || 'Invalid request. Please check your location and try again.';
    }

    if (status === 403) {
      if (detailStr.toLowerCase().includes('resolve') || detailStr.toLowerCase().includes('resolution')) {
        return 'Only the original reporter, verified ambulance operators, or admins can resolve this incident.';
      }
      return 'You do not have permission to perform this action.';
    }

    if (status === 429) {
      const retryAfter = error.response?.headers?.['retry-after'];
      if (retryAfter) {
        return `Rate limit exceeded. Please wait ${retryAfter} seconds before trying again.`;
      }
      return 'Too many requests. Please wait a moment before trying again.';
    }

    if (status === 404 || status === 410) {
      return 'This incident has expired or no longer exists.';
    }

    if (detailStr) {
      return detailStr;
    }
  }

  if (error instanceof Error) {
    return error.message;
  }

  return 'An unexpected network error occurred. Please try again.';
}
