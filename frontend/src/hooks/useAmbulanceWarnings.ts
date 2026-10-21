import { useState, useEffect, useRef, useCallback } from 'react';
import { WsAmbulanceNearbyMessage, WsServerMessage } from '@/types/dispatch';
import { RealtimeClient } from '@/realtime/RealtimeClient';

export interface ActiveAmbulanceWarning {
  distance_m: number;
  bearing_deg: number;
  approaching: boolean;
  expires_in_s: number;
  received_at: number;
}

interface UseAmbulanceWarningsProps {
  realtimeClient?: RealtimeClient | null;
}

export function useAmbulanceWarnings({ realtimeClient }: UseAmbulanceWarningsProps) {
  const [warning, setWarning] = useState<ActiveAmbulanceWarning | null>(null);
  const [isDismissed, setIsDismissed] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const previousWarningRef = useRef<ActiveAmbulanceWarning | null>(null);

  const clearTimer = () => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  };

  const handleNearby = useCallback((msg: WsAmbulanceNearbyMessage) => {
    // Vibrate once on first transition from no warning to active warning
    if (!previousWarningRef.current && typeof navigator !== 'undefined' && 'vibrate' in navigator) {
      try {
        navigator.vibrate([200, 100, 200]);
      } catch {}
    }

    const newWarning: ActiveAmbulanceWarning = {
      distance_m: msg.distance_m,
      bearing_deg: msg.bearing_deg,
      approaching: msg.approaching,
      expires_in_s: msg.expires_in_s || 10,
      received_at: Date.now(),
    };

    previousWarningRef.current = newWarning;
    setWarning(newWarning);
    setIsDismissed(false);

    // Auto-hide when expires_in_s elapses without a fresh update
    clearTimer();
    const timeoutMs = (msg.expires_in_s || 10) * 1000;
    timerRef.current = setTimeout(() => {
      setWarning(null);
      previousWarningRef.current = null;
    }, timeoutMs);
  }, []);

  const handleClear = useCallback(() => {
    clearTimer();
    setWarning(null);
    previousWarningRef.current = null;
  }, []);

  useEffect(() => {
    if (!realtimeClient) return;

    const unsubscribe = realtimeClient.addListener((msg: WsServerMessage) => {
      if (msg.type === 'ambulance.nearby') {
        handleNearby(msg as WsAmbulanceNearbyMessage);
      } else if (msg.type === 'ambulance.clear') {
        handleClear();
      }
    });

    return () => {
      unsubscribe();
      clearTimer();
    };
  }, [realtimeClient, handleNearby, handleClear]);

  const dismiss = () => {
    setIsDismissed(true);
  };

  return {
    warning: isDismissed ? null : warning,
    dismiss,
    handleNearby,
    handleClear,
  };
}
