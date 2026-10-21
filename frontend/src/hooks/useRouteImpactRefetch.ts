import { useRef, useCallback, useEffect } from 'react';

export interface UseRouteImpactRefetchOptions {
  hasActiveRoute: boolean;
  refetchRoutes: () => Promise<unknown> | void;
  debounceMs?: number; // default 3000 ms
  throttleMs?: number; // default 10000 ms
}

/**
 * Hook to handle realtime route_impact notifications:
 * Debounces execution by 3 seconds, and throttles refetches to at most once per 10 seconds.
 */
export function useRouteImpactRefetch({
  hasActiveRoute,
  refetchRoutes,
  debounceMs = 3000,
  throttleMs = 10000,
}: UseRouteImpactRefetchOptions) {
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const throttleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastRefetchTimeRef = useRef<number>(0);
  const refetchRoutesRef = useRef(refetchRoutes);
  refetchRoutesRef.current = refetchRoutes;

  const triggerRefetch = useCallback(() => {
    const now = Date.now();
    lastRefetchTimeRef.current = now;
    refetchRoutesRef.current();
  }, []);

  const handleRouteImpact = useCallback(() => {
    if (!hasActiveRoute) return;

    // Reset 3s debounce timer
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
      debounceTimerRef.current = null;
    }

    debounceTimerRef.current = setTimeout(() => {
      const now = Date.now();
      const timeSinceLast = now - lastRefetchTimeRef.current;

      if (timeSinceLast >= throttleMs) {
        triggerRefetch();
      } else {
        // Enforce throttle: schedule for when the 10s cooldown expires
        if (!throttleTimerRef.current) {
          const waitMs = throttleMs - timeSinceLast;
          throttleTimerRef.current = setTimeout(() => {
            throttleTimerRef.current = null;
            triggerRefetch();
          }, waitMs);
        }
      }
    }, debounceMs);
  }, [hasActiveRoute, debounceMs, throttleMs, triggerRefetch]);

  // Clean up timers on unmount
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
      if (throttleTimerRef.current) clearTimeout(throttleTimerRef.current);
    };
  }, []);

  return { handleRouteImpact };
}
