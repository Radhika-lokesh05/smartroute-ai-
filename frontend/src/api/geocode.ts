import { apiClient } from './client';
import { GeocodeResponse } from '@/types/geocode';

export async function fetchAutocomplete(
  q: string,
  focus_lat?: number,
  focus_lng?: number,
  signal?: AbortSignal
): Promise<GeocodeResponse> {
  const params: Record<string, string | number> = { q };
  if (focus_lat !== undefined && focus_lng !== undefined) {
    params.focus_lat = focus_lat;
    params.focus_lng = focus_lng;
  }
  const response = await apiClient.get<GeocodeResponse>('/api/geocode/autocomplete', {
    params,
    signal,
  });
  return response.data;
}

export async function fetchGeocodeSearch(
  q: string,
  signal?: AbortSignal
): Promise<GeocodeResponse> {
  const response = await apiClient.get<GeocodeResponse>('/api/geocode/search', {
    params: { q },
    signal,
  });
  return response.data;
}

export async function fetchReverseGeocode(
  lat: number,
  lng: number,
  signal?: AbortSignal
): Promise<GeocodeResponse> {
  const response = await apiClient.get<GeocodeResponse>('/api/geocode/reverse', {
    params: { lat, lng },
    signal,
  });
  return response.data;
}
