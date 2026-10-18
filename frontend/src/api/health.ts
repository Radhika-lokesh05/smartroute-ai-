import { apiClient } from './client';
import { HealthResponse } from '@/types/health';

/**
 * Fetch health status from FastAPI backend /health endpoint.
 */
export async function getHealthStatus(): Promise<HealthResponse> {
  const response = await apiClient.get<HealthResponse>('/health');
  return response.data;
}
