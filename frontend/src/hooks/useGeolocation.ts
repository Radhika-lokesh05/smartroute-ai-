import { useState, useEffect, useCallback } from 'react';

export interface UserLocation {
  lat: number;
  lng: number;
  accuracy: number;
  heading?: number | null;
}

export function useGeolocation() {
  const [location, setLocation] = useState<UserLocation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLocating, setIsLocating] = useState<boolean>(false);

  const isSecureContext = window.isSecureContext || window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';

  const handleError = useCallback((err: GeolocationPositionError) => {
    let message = 'Unable to determine your location.';
    if (err.code === err.PERMISSION_DENIED) {
      message = 'Location access was denied. Please enable location permissions.';
    } else if (err.code === err.POSITION_UNAVAILABLE) {
      message = 'GPS location is currently unavailable.';
    } else if (err.code === err.TIMEOUT) {
      message = 'GPS location request timed out.';
    }
    if (!isSecureContext) {
      message += ' Note: GPS geolocation requires an HTTPS connection or localhost.';
    }
    setError(message);
    setIsLocating(false);
  }, [isSecureContext]);

  useEffect(() => {
    if (!navigator.geolocation) {
      setError('Geolocation is not supported by your browser.');
      return;
    }

    const watchId = navigator.geolocation.watchPosition(
      (position) => {
        setLocation({
          lat: position.coords.latitude,
          lng: position.coords.longitude,
          accuracy: position.coords.accuracy,
          heading: position.coords.heading,
        });
        setError(null);
      },
      handleError,
      {
        enableHighAccuracy: true,
        maximumAge: 10000,
        timeout: 15000,
      }
    );

    return () => {
      navigator.geolocation.clearWatch(watchId);
    };
  }, [handleError]);

  const locateMe = useCallback(() => {
    if (!navigator.geolocation) {
      setError('Geolocation is not supported by your browser.');
      return;
    }
    setIsLocating(true);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLocation({
          lat: position.coords.latitude,
          lng: position.coords.longitude,
          accuracy: position.coords.accuracy,
          heading: position.coords.heading,
        });
        setError(null);
        setIsLocating(false);
      },
      handleError,
      {
        enableHighAccuracy: true,
        timeout: 10000,
      }
    );
  }, [handleError]);

  return { location, error, isLocating, locateMe, isSecureContext };
}
