import { useQuery } from '@tanstack/react-query';
import { fetchRoutes } from '@/api/routes';
import { RouteResponse, WayPoint } from '@/types/routing';

interface UseRoutesProps {
  origin: WayPoint | null;
  destination: WayPoint | null;
  departureTime?: string;
}

export function useRoutesQuery({ origin, destination, departureTime }: UseRoutesProps) {
  const isEnabled = Boolean(
    origin &&
    destination &&
    typeof origin.lat === 'number' &&
    typeof origin.lng === 'number' &&
    typeof destination.lat === 'number' &&
    typeof destination.lng === 'number'
  );

  return useQuery<RouteResponse, Error>({
    queryKey: [
      'routes',
      origin ? `${origin.lat.toFixed(5)},${origin.lng.toFixed(5)}` : null,
      destination ? `${destination.lat.toFixed(5)},${destination.lng.toFixed(5)}` : null,
      departureTime || 'now',
    ],
    queryFn: async ({ signal }) => {
      if (!origin || !destination) {
        throw new Error('Both origin and destination coordinates are required.');
      }
      return fetchRoutes(
        origin.lat,
        origin.lng,
        destination.lat,
        destination.lng,
        signal,
        true,
        departureTime
      );
    },
    enabled: isEnabled,
    staleTime: 60000,
    retry: (failureCount, error: any) => {
      // Do not retry 404 (no route) or 429 (rate limit)
      const status = error?.response?.status;
      if (status === 404 || status === 429) return false;
      return failureCount < 1;
    },
  });
}
