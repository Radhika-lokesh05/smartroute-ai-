import { useQuery } from '@tanstack/react-query';
import { getNearbyHospitals } from '@/api/hospitals';
import { HospitalNearbyResponse } from '@/types/hospital';

interface UseNearbyHospitalsQueryProps {
  lat?: number | null;
  lng?: number | null;
  emergencyType?: string;
}

export function useNearbyHospitalsQuery({
  lat,
  lng,
  emergencyType = 'general',
}: UseNearbyHospitalsQueryProps) {
  // Round coordinates to ~1 km grid (0.01 deg) for query caching and refetching
  const latRounded = lat != null ? Math.round(lat * 100) / 100 : null;
  const lngRounded = lng != null ? Math.round(lng * 100) / 100 : null;

  return useQuery<HospitalNearbyResponse>({
    queryKey: ['hospitals', 'nearby', latRounded, lngRounded, emergencyType],
    queryFn: () => {
      if (lat == null || lng == null) {
        throw new Error('User coordinates required for hospital search.');
      }
      return getNearbyHospitals(lat, lng, emergencyType);
    },
    enabled: lat != null && lng != null,
    staleTime: 30000, // Cache results for 30 seconds
    retry: 1,
  });
}
