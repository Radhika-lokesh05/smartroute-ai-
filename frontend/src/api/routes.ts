import { apiClient } from './client';
import { RouteResponse } from '@/types/routing';

export interface FetchRoutesOptions {
  from_lat: number;
  from_lng: number;
  to_lat: number;
  to_lng: number;
  departure_time?: string;
  use_incidents?: boolean;
  avoid_polygons_json?: string;
  signal?: AbortSignal;
}

export async function fetchRoutes(
  from_lat: number,
  from_lng: number,
  to_lat: number,
  to_lng: number,
  signal?: AbortSignal,
  use_incidents: boolean = true,
  departure_time?: string
): Promise<RouteResponse> {
  const params: Record<string, unknown> = {
    from_lat,
    from_lng,
    to_lat,
    to_lng,
    use_incidents,
  };
  if (departure_time) {
    params.departure_time = departure_time;
  }
  const response = await apiClient.get<RouteResponse>('/api/routes', {
    params,
    signal,
  });
  return response.data;
}
