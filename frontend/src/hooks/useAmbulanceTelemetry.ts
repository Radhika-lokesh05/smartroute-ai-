import { useState, useEffect, useRef, useCallback } from 'react';
import { AmbulanceStatus } from '@/types/dispatch';
import { setAmbulanceStatus } from '@/api/dispatch';
import { RealtimeClient } from '@/realtime/RealtimeClient';

export interface TelemetryCoords {
  lat: number;
  lng: number;
  accuracy: number;
  heading: number;
  speed: number;
}

interface UseAmbulanceTelemetryProps {
  initialStatus?: AmbulanceStatus;
  realtimeClient?: RealtimeClient | null;
}

export function useAmbulanceTelemetry({
  initialStatus = 'offline',
  realtimeClient,
}: UseAmbulanceTelemetryProps) {
  const [status, setStatusState] = useState<AmbulanceStatus>(initialStatus);
  const [coords, setCoords] = useState<TelemetryCoords | null>(null);
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false);
  const [isTabHidden, setIsTabHidden] = useState(false);
  const [telemetryError, setTelemetryError] = useState<string | null>(null);

  const watchIdRef = useRef<number | null>(null);
  const lastSentTimeRef = useRef<number>(0);
  const wakeLockRef = useRef<any>(null);

  // Sync initial status when profile loads
  useEffect(() => {
    if (initialStatus) {
      setStatusState(initialStatus);
    }
  }, [initialStatus]);

  // Request & release screen Wake Lock
  const requestWakeLock = async () => {
    if ('wakeLock' in navigator && !wakeLockRef.current) {
      try {
        wakeLockRef.current = await (navigator as any).wakeLock.request('screen');
      } catch {
        // Silently ignore denial
      }
    }
  };

  const releaseWakeLock = () => {
    if (wakeLockRef.current) {
      try {
        wakeLockRef.current.release();
      } catch {}
      wakeLockRef.current = null;
    }
  };

  // Monitor tab visibility
  useEffect(() => {
    const handleVisibility = () => {
      setIsTabHidden(document.hidden);
    };
    document.addEventListener('visibilitychange', handleVisibility);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, []);

  // Send throttled location update
  const handlePositionUpdate = useCallback(
    (position: GeolocationPosition) => {
      const { latitude: lat, longitude: lng, accuracy, heading, speed } = position.coords;
      const cleanHeading = heading != null && !Number.isNaN(heading) ? heading : 0;
      const cleanSpeed = speed != null && !Number.isNaN(speed) ? Math.max(0, speed * 3.6) : 0; // km/h

      setCoords({ lat, lng, accuracy, heading: cleanHeading, speed: cleanSpeed });
      setTelemetryError(null);

      // Backend minimum interval throttle: 2 seconds
      const now = Date.now();
      if (now - lastSentTimeRef.current >= 2000 && realtimeClient) {
        realtimeClient.sendLocation(lat, lng, cleanHeading, cleanSpeed);
        lastSentTimeRef.current = now;
      }
    },
    [realtimeClient]
  );

  // Start or stop geolocation watching depending on status
  useEffect(() => {
    const isOnline = status === 'available' || status === 'busy';

    const stopWatching = () => {
      if (watchIdRef.current !== null) {
        if (typeof navigator !== 'undefined' && navigator.geolocation?.clearWatch) {
          navigator.geolocation.clearWatch(watchIdRef.current);
        }
        watchIdRef.current = null;
      }
      releaseWakeLock();
    };

    if (isOnline && typeof navigator !== 'undefined' && 'geolocation' in navigator) {
      requestWakeLock();
      watchIdRef.current = navigator.geolocation.watchPosition(
        handlePositionUpdate,
        (err) => {
          setTelemetryError(err.message || 'GPS telemetry signal lost');
        },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 1000 }
      );
    } else {
      stopWatching();
    }

    return () => {
      stopWatching();
    };
  }, [status, handlePositionUpdate]);

  // Toggle online availability
  const updateStatus = async (target: 'available' | 'offline') => {
    if (target === 'available' && !coords) {
      throw new Error('A valid GPS fix is required to go Available.');
    }
    setIsUpdatingStatus(true);
    setTelemetryError(null);
    try {
      const res = await setAmbulanceStatus(target);
      setStatusState(res.status);
    } catch (err: any) {
      setTelemetryError(err.message || 'Failed to update status');
      throw err;
    } finally {
      setIsUpdatingStatus(false);
    }
  };

  return {
    status,
    setStatusState,
    coords,
    isUpdatingStatus,
    isTabHidden,
    telemetryError,
    updateStatus,
  };
}
