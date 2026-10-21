import { apiClient } from './client';
import { HospitalNearbyResponse } from '@/types/hospital';

/**
 * Fetch nearby emergency hospitals ranked by adjusted ETA including
 * real-time traffic and active road incident delays.
 */
export async function getNearbyHospitals(
  lat: number,
  lng: number,
  emergencyType?: string
): Promise<HospitalNearbyResponse> {
  const params: Record<string, string | number> = { lat, lng };
  if (emergencyType && emergencyType !== 'general') {
    params.emergency_type = emergencyType;
  }
  const response = await apiClient.get<HospitalNearbyResponse>('/api/hospitals/nearby', {
    params,
  });
  return response.data;
}
