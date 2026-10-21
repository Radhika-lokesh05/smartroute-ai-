import { isAxiosError } from 'axios';
import { apiClient } from './client';
import { AmbulanceRecord, AmbulanceStatus, DispatchResponse } from '@/types/dispatch';

/**
 * Fetch the currently active dispatch for the authenticated ambulance operator.
 * Returns null if no dispatch is currently active (404).
 */
export async function getCurrentDispatch(): Promise<DispatchResponse | null> {
  try {
    const res = await apiClient.get<DispatchResponse>('/api/dispatches/active');
    return res.data;
  } catch (error) {
    if (isAxiosError(error) && error.response?.status === 404) {
      return null;
    }
    throw error;
  }
}

/**
 * Accept an incoming dispatch offer. Transitions dispatch to 'en_route_to_scene'.
 */
export async function acceptDispatch(id: string): Promise<DispatchResponse> {
  const res = await apiClient.post<DispatchResponse>(`/api/dispatches/${id}/accept`);
  return res.data;
}

/**
 * Decline an incoming dispatch offer with an optional reason.
 */
export async function declineDispatch(id: string, reason?: string): Promise<DispatchResponse> {
  const res = await apiClient.post<DispatchResponse>(`/api/dispatches/${id}/decline`, {
    reason,
  });
  return res.data;
}

/**
 * Advance dispatch lifecycle status ('at_scene', 'to_hospital', 'completed', 'cancelled').
 */
export async function updateDispatchStatus(
  id: string,
  status: string,
  hospital_id?: string
): Promise<DispatchResponse> {
  const payload: { status: string; hospital_id?: string } = { status };
  if (hospital_id) {
    payload.hospital_id = hospital_id;
  }
  const res = await apiClient.patch<DispatchResponse>(`/api/dispatches/${id}/progress`, payload);
  return res.data;
}

/**
 * Toggle ambulance operator status ('available' | 'offline').
 */
export async function setAmbulanceStatus(status: AmbulanceStatus): Promise<AmbulanceRecord> {
  const res = await apiClient.patch<AmbulanceRecord>('/api/ambulance/status', { status });
  return res.data;
}

/**
 * Retrieve the current ambulance profile linked to authenticated operator.
 */
export async function getMyAmbulance(): Promise<AmbulanceRecord> {
  const res = await apiClient.get<AmbulanceRecord>('/api/ambulance/me');
  return res.data;
}

/**
 * Maps server HTTP errors to user-friendly messages.
 */
export function mapDispatchError(error: unknown): string {
  if (isAxiosError(error) && error.response) {
    const status = error.response.status;
    const detail = (error.response.data as { detail?: string })?.detail;

    if (status === 403) {
      return 'Account not verified for emergency operations.';
    }
    if (status === 409 || (status === 400 && detail?.toLowerCase().includes('already taken'))) {
      return 'Invalid dispatch state or offer already claimed by another unit.';
    }
    if (status === 404) {
      return 'Dispatch offer has expired or is no longer available.';
    }
    if (detail) {
      return detail;
    }
  }
  return 'An unexpected emergency dispatch error occurred. Please try again.';
}
