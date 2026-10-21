import { useQuery } from '@tanstack/react-query';
import { getMyAmbulance } from '@/api/dispatch';
import { AmbulanceRecord } from '@/types/dispatch';

export function useAmbulanceProfile() {
  const query = useQuery<AmbulanceRecord>({
    queryKey: ['ambulance', 'me'],
    queryFn: getMyAmbulance,
    staleTime: 60000,
    retry: 1,
  });

  return {
    ambulance: query.data,
    isVerified: query.data?.is_verified ?? false,
    status: query.data?.status ?? 'offline',
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}
