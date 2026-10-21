import { useQuery } from '@tanstack/react-query';
import { getNearbyIncidents } from '@/api/incidents';
import { Incident } from '@/types/incident';

export function useNearbyIncidentsQuery(
  userLocation: { lat: number; lng: number } | null,
  radiusM = 5000
) {
  return useQuery<Incident[], Error>({
    queryKey: ['incidents', 'nearby', userLocation?.lat, userLocation?.lng, radiusM],
    queryFn: async () => {
      if (!userLocation) return [];
      return getNearbyIncidents(userLocation.lat, userLocation.lng, radiusM);
    },
    enabled: !!userLocation,
    staleTime: 60000,
    refetchOnWindowFocus: true,
  });
}
