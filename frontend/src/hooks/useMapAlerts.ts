import { useState, useCallback } from 'react';
import { IncidentToastItem } from '@/components/incidents/IncidentToasts';
import { WsIncidentEventMessage } from '@/types/incident';
import { UserLocation } from '@/hooks/useGeolocation';
import { calculateDistanceM, LeafletCoord } from '@/utils/coordinates';
import { playAlertSound } from '@/utils/sound';

export function useMapAlerts(userLocation: UserLocation | null, isSoundEnabled: boolean) {
  const [toasts, setToasts] = useState<IncidentToastItem[]>([]);
  const [focusedLocation, setFocusedLocation] = useState<LeafletCoord | null>(null);

  const handleAlert = useCallback(
    (msg: WsIncidentEventMessage) => {
      if (msg.type !== 'incident.created' && msg.type !== 'incident.validated') return;

      let distM: number | null = null;
      if (userLocation) {
        distM = calculateDistanceM(userLocation.lat, userLocation.lng, msg.data.lat, msg.data.lng);
        if (distM > 3000) return; // Alert within 3 km only
      }

      const toastId = `${msg.data.id}-${msg.type}`;
      setToasts((prev) => {
        const filtered = prev.filter((t) => t.incidentId !== msg.data.id);
        const newToast: IncidentToastItem = {
          id: toastId,
          incidentId: msg.data.id,
          eventType: msg.type,
          incidentType: msg.data.incident_type,
          note: msg.data.note,
          lat: msg.data.lat,
          lng: msg.data.lng,
          distanceM: distM,
        };
        return [newToast, ...filtered].slice(0, 3);
      });

      if (isSoundEnabled) {
        playAlertSound();
      }
    },
    [userLocation, isSoundEnabled]
  );

  const handleDismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const handleShowOnMap = useCallback((lat: number, lng: number) => {
    setFocusedLocation([lat, lng]);
  }, []);

  const addReportToast = useCallback((msg: string, lat: number, lng: number) => {
    setToasts((prev) => [
      {
        id: `report-success-${Date.now()}`,
        incidentId: 'new',
        eventType: 'incident.created',
        incidentType: 'accident',
        note: msg,
        lat,
        lng,
      },
      ...prev,
    ]);
  }, []);

  return {
    toasts,
    focusedLocation,
    setFocusedLocation,
    handleAlert,
    handleDismissToast,
    handleShowOnMap,
    addReportToast,
  };
}
