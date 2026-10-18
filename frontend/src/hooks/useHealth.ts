import { useQuery } from '@tanstack/react-query';
import { getHealthStatus } from '@/api/health';
import { HealthResponse } from '@/types/health';

export function useHealth() {
  return useQuery<HealthResponse, Error>({
    queryKey: ['health'],
    queryFn: getHealthStatus,
    refetchInterval: 5000, // Poll every 5 seconds
    retry: 1,
    staleTime: 4000,
  });
}
