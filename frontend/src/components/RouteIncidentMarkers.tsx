import React from 'react';
import { Marker, Popup, CircleMarker } from 'react-leaflet';
import L from 'leaflet';
import { IncidentOnRoute } from '@/types/routing';

interface RouteIncidentMarkersProps {
  incidents: IncidentOnRoute[];
}

function createRouteIncidentIcon(type: string) {
  const isAccident = type === 'accident';
  const isBlockage = type === 'blockage';
  const colorClass = isAccident ? 'bg-rose-500' : isBlockage ? 'bg-amber-500' : 'bg-yellow-500';

  return L.divIcon({
    className: 'route-incident-icon',
    html: `
      <div class="relative flex items-center justify-center">
        <div class="absolute w-7 h-7 rounded-full ${colorClass} opacity-40 animate-ping"></div>
        <div class="relative w-5 h-5 rounded-full ${colorClass} border-2 border-white shadow-lg flex items-center justify-center text-white text-[10px] font-bold">
          !
        </div>
      </div>
    `,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  });
}

export const RouteIncidentMarkers: React.FC<RouteIncidentMarkersProps> = ({ incidents }) => {
  if (!incidents || incidents.length === 0) return null;

  return (
    <>
      {incidents.map((inc) => (
        <React.Fragment key={`route-inc-${inc.id}`}>
          <CircleMarker
            center={[inc.lat, inc.lng]}
            radius={24}
            pathOptions={{
              color: '#f59e0b',
              fillColor: '#f59e0b',
              fillOpacity: 0.2,
              weight: 2,
              dashArray: '3, 3',
            }}
          />
          <Marker
            position={[inc.lat, inc.lng]}
            icon={createRouteIncidentIcon(inc.type)}
          >
            <Popup className="incident-popup">
              <div className="p-1 text-xs">
                <span className="font-bold capitalize text-amber-400">
                  {inc.type} on Route
                </span>
                <p className="text-[11px] text-slate-300 mt-0.5">
                  Status: <span className="font-semibold">{inc.status}</span>
                </p>
                <p className="text-[10px] text-slate-400">
                  {Math.round(inc.distance_from_route_m)}m from road line
                </p>
              </div>
            </Popup>
          </Marker>
        </React.Fragment>
      ))}
    </>
  );
};
