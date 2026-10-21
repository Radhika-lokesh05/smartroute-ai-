import React, { useMemo } from 'react';
import { Marker, Popup } from 'react-leaflet';
import { Incident } from '@/types/incident';
import { createIncidentDivIcon } from './incidentIcons';
import { IncidentPopup } from './IncidentPopup';

interface IncidentMarkersProps {
  incidents: Incident[];
  userLocation: { lat: number; lng: number } | null;
}

const MAX_DISPLAY_MARKERS = 100;

export const IncidentMarkers: React.FC<IncidentMarkersProps> = ({ incidents, userLocation }) => {
  // Cap at 100 closest markers to preserve 60fps map rendering performance
  const visibleIncidents = useMemo(() => {
    return incidents.slice(0, MAX_DISPLAY_MARKERS);
  }, [incidents]);

  return (
    <>
      {visibleIncidents.map((incident) => {
        const icon = createIncidentDivIcon(incident.incident_type, incident.status);
        return (
          <Marker
            key={incident.id}
            position={[incident.lat, incident.lng]}
            icon={icon}
          >
            <Popup className="dark-popup" minWidth={220} maxWidth={280}>
              <IncidentPopup incident={incident} userLocation={userLocation} />
            </Popup>
          </Marker>
        );
      })}
    </>
  );
};
