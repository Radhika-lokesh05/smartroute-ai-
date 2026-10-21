import { useEffect, useRef, useState, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/auth/useAuth';
import { API_BASE_URL } from '@/api/client';
import { RealtimeClient } from './RealtimeClient';
import { mergeIncidentIntoCache } from './cacheMerge';
import {
  Incident,
  RealtimeConnectionStatus,
  WsIncidentEventMessage,
} from '@/types/incident';

export interface UseRealtimeIncidentsOptions {
  userLocation?: { lat: number; lng: number } | null;
  onAlert?: (event: WsIncidentEventMessage) => void;
  onRouteImpact?: (event: WsIncidentEventMessage) => void;
}

export function useRealtimeIncidents({ userLocation, onAlert, onRouteImpact }: UseRealtimeIncidentsOptions = {}) {
  const { user, logout } = useAuth();
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<RealtimeConnectionStatus>('offline');

  const clientRef = useRef<RealtimeClient | null>(null);
  const onAlertRef = useRef(onAlert);
  onAlertRef.current = onAlert;
  const onRouteImpactRef = useRef(onRouteImpact);
  onRouteImpactRef.current = onRouteImpact;
  const userLocationRef = useRef(userLocation);
  userLocationRef.current = userLocation;

  // Handle incoming incident events from WebSocket
  const handleIncidentEvent = useCallback(
    (message: WsIncidentEventMessage) => {
      // 1. Update TanStack Query cache for all ['incidents', 'nearby'] queries
      queryClient.setQueriesData<Incident[]>(
        { queryKey: ['incidents', 'nearby'] },
        (oldIncidents = []) => {
          return mergeIncidentIntoCache(
            oldIncidents,
            message.type,
            message.data,
            userLocationRef.current
          );
        }
      );

      // 2. Dispatch route impact callback if flagged
      if (message.route_impact) {
        onRouteImpactRef.current?.(message);
      }

      // 3. Dispatch alert callback if requested
      onAlertRef.current?.(message);
    },
    [queryClient]
  );


  // Handle reconnect: re-fetch nearby queries to bridge any dropped events
  const handleReconnect = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['incidents', 'nearby'] });
  }, [queryClient]);

  // Handle 4401 auth failure: log the user out
  const handleAuthFailed = useCallback(() => {
    logout();
  }, [logout]);

  const [clientInstance, setClientInstance] = useState<RealtimeClient | null>(null);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token || !user) {
      if (clientRef.current) {
        clientRef.current.disconnect();
        clientRef.current = null;
        setClientInstance(null);
      }
      setStatus('offline');
      return;
    }

    // Reuse existing client or create new instance (Strict-mode safe)
    if (!clientRef.current) {
      const client = new RealtimeClient({
        apiBaseUrl: API_BASE_URL,
        token,
        onStatusChange: (newStatus) => setStatus(newStatus),
        onIncidentEvent: handleIncidentEvent,
        onReconnect: handleReconnect,
        onAuthFailed: handleAuthFailed,
      });
      clientRef.current = client;
      setClientInstance(client);
      client.connect();
    } else {
      clientRef.current.updateToken(token);
    }

    return () => {
      if (clientRef.current) {
        clientRef.current.disconnect();
        clientRef.current = null;
        setClientInstance(null);
      }
    };
  }, [user, handleIncidentEvent, handleReconnect, handleAuthFailed]);

  // Keep subscription in sync when user location updates (throttled inside RealtimeClient)
  useEffect(() => {
    if (clientRef.current && userLocation) {
      clientRef.current.subscribe(userLocation.lat, userLocation.lng);
    }
  }, [userLocation]);

  return { status, realtimeClient: clientInstance };
}
