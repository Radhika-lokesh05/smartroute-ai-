import { useEffect, useRef, useState } from 'react';
import { RealtimeClient } from '@/realtime/RealtimeClient';
import { API_BASE_URL } from '@/api/client';
import { IncidentPublic } from '@/types/incident';

export interface LiveAmbulance {
  id: string;
  plate: string;
  lat: number;
  lng: number;
  status: string;
  heading?: number;
  lastUpdated: string;
}

export function useAdminRealtime() {
  const [incidents, setIncidents] = useState<Record<string, IncidentPublic>>({});
  const [ambulances, setAmbulances] = useState<Record<string, LiveAmbulance>>({});
  const [connected, setConnected] = useState<boolean>(false);
  const clientRef = useRef<RealtimeClient | null>(null);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) return;

    const client = new RealtimeClient({
      apiBaseUrl: API_BASE_URL,
      token,
      onStatusChange: (status) => setConnected(status === 'connected' || status === 'live'),
      onIncidentEvent: (msg) => {
        const inc = msg.data as IncidentPublic;
        if (!inc || !inc.id) return;
        setIncidents((prev) => {
          if (inc.status === 'resolved' || inc.status === 'expired') {
            const next = { ...prev };
            delete next[inc.id];
            return next;
          }
          return { ...prev, [inc.id]: inc };
        });
      },
      onAnyMessage: (raw: any) => {
        if (raw?.type === 'ambulance.location' || raw?.data?.ambulance_id) {
          const d = raw.data || {};
          const ambId = d.ambulance_id || d.id || 'unknown';
          if (d.lat && d.lng) {
            setAmbulances((prev) => ({
              ...prev,
              [ambId]: {
                id: ambId,
                plate: d.plate_number || d.plate || 'AMB',
                lat: Number(d.lat),
                lng: Number(d.lng),
                status: d.status || 'active',
                heading: d.heading,
                lastUpdated: new Date().toLocaleTimeString(),
              },
            }));
          }
        }
      },
    });

    client.connect();
    // Admin city-wide subscription
    client.subscribeArea(12.9716, 77.5946, 50000);
    clientRef.current = client;

    return () => {
      client.disconnect();
      clientRef.current = null;
    };
  }, []);

  return { incidents: Object.values(incidents), ambulances: Object.values(ambulances), connected };
}
