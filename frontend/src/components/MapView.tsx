import React, { useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Polyline, Circle, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import { WayPoint, RouteItem } from '@/types/routing';
import { Incident } from '@/types/incident';
import { UserLocation } from '@/hooks/useGeolocation';
import { geojsonCoordsToLeaflet, LeafletCoord } from '@/utils/coordinates';
import { originIcon, destinationIcon, userLocationIcon } from '@/utils/leafletIcons';
import { IncidentMarkers } from './incidents/IncidentMarkers';
import { RouteIncidentMarkers } from './RouteIncidentMarkers';
import { MapRouteLegend } from './MapRouteLegend';
import { Crosshair, AlertCircle, ShieldAlert } from 'lucide-react';
import { TILE_URL, TILE_ATTRIBUTION } from '@/constants/map';

interface MapViewProps {
  origin: WayPoint | null;
  destination: WayPoint | null;
  routes: RouteItem[];
  selectedIndex: number;
  userLocation: UserLocation | null;
  incidents?: Incident[];
  focusedLocation?: LeafletCoord | null;
  onMapClick: (lat: number, lng: number) => void;
  onLocateMe: () => void;
  onOpenReportModal?: () => void;
  isLocating: boolean;
  gpsError: string | null;
  isSecureContext: boolean;
}

const DEFAULT_CENTER: LeafletCoord = [12.9716, 77.5946];

function MapController({ routeCoords, userLoc, focusedLoc }: { routeCoords?: LeafletCoord[]; userLoc?: LeafletCoord; focusedLoc?: LeafletCoord | null; }) {
  const map = useMap();
  useEffect(() => {
    if (focusedLoc) map.setView(focusedLoc, 16, { animate: true });
  }, [map, focusedLoc]);
  useEffect(() => {
    if (routeCoords && routeCoords.length > 0 && !focusedLoc) {
      map.fitBounds(L.latLngBounds(routeCoords), { padding: [60, 60], maxZoom: 16 });
    }
  }, [map, routeCoords, focusedLoc]);
  useEffect(() => {
    if (userLoc && (!routeCoords || routeCoords.length === 0) && !focusedLoc) {
      map.setView(userLoc, 15);
    }
  }, [map, userLoc, routeCoords, focusedLoc]);
  return null;
}

function ClickHandler({ onMapClick }: { onMapClick: (lat: number, lng: number) => void }) {
  useMapEvents({ click(e) { onMapClick(e.latlng.lat, e.latlng.lng); } });
  return null;
}

export const MapView: React.FC<MapViewProps> = ({
  origin, destination, routes, selectedIndex, userLocation, incidents = [],
  focusedLocation, onMapClick, onLocateMe, onOpenReportModal, isLocating, gpsError, isSecureContext,
}) => {
  const selectedRoute = routes[selectedIndex];
  const selectedCoords = selectedRoute ? geojsonCoordsToLeaflet(selectedRoute.geometry.coordinates) : undefined;
  const isSelectedRecommended = selectedRoute ? (selectedRoute.rank === 1 || selectedIndex === 0) : false;

  return (
    <div className="relative w-full h-full min-h-[400px]">
      <MapContainer center={DEFAULT_CENTER} zoom={13} scrollWheelZoom={true} className="w-full h-full z-0 bg-slate-950">
        <TileLayer attribution={TILE_ATTRIBUTION} url={TILE_URL} className="dark-tiles" />
        <MapController routeCoords={selectedCoords} userLoc={userLocation ? [userLocation.lat, userLocation.lng] : undefined} focusedLoc={focusedLocation} />
        <ClickHandler onMapClick={onMapClick} />

        {userLocation && (
          <>
            <Circle center={[userLocation.lat, userLocation.lng]} radius={userLocation.accuracy} pathOptions={{ color: '#06B6D4', fillColor: '#06B6D4', fillOpacity: 0.12, weight: 1.5 }} />
            <Marker position={[userLocation.lat, userLocation.lng]} icon={userLocationIcon} />
          </>
        )}

        {origin && <Marker position={[origin.lat, origin.lng]} icon={originIcon} />}
        {destination && <Marker position={[destination.lat, destination.lng]} icon={destinationIcon} />}

        {/* Incidents markers and active route highlighted incidents */}
        <IncidentMarkers incidents={incidents} userLocation={userLocation} />
        {selectedRoute?.incidents_on_route && (
          <RouteIncidentMarkers incidents={selectedRoute.incidents_on_route} />
        )}

        {/* Alternative Routes: Recommended route is drawn thicker */}
        {routes.map((route, idx) => {
          if (idx === selectedIndex) return null;
          const coords = geojsonCoordsToLeaflet(route.geometry.coordinates);
          const isRec = route.rank === 1 || idx === 0;
          return (
            <Polyline
              key={`alt-${idx}`}
              positions={coords}
              pathOptions={{
                color: isRec ? '#0891b2' : '#64748b',
                weight: isRec ? 6 : 4,
                opacity: isRec ? 0.8 : 0.55,
                dashArray: isRec ? undefined : '6, 6',
              }}
            />
          );
        })}

        {/* Selected Route Polyline (Thicker when recommended) */}
        {selectedCoords && (
          <Polyline
            positions={selectedCoords}
            pathOptions={{ color: '#06B6D4', weight: isSelectedRecommended ? 8 : 6, opacity: 0.95 }}
          />
        )}
      </MapContainer>

      {/* Map Legend */}
      <div className="absolute bottom-6 left-6 z-10 pointer-events-auto">
        <MapRouteLegend />
      </div>

      {/* Floating Controls */}
      <div className="absolute top-4 right-4 z-10 flex flex-col items-end gap-2 pointer-events-auto">
        <button type="button" onClick={onLocateMe} disabled={isLocating} className="p-2.5 rounded-xl bg-slate-900/90 hover:bg-slate-800 text-cyan-400 border border-slate-700 shadow-xl backdrop-blur-md transition-all active:scale-95 disabled:opacity-50">
          <Crosshair className={`w-5 h-5 ${isLocating ? 'animate-spin' : ''}`} />
        </button>
        {gpsError && <div className="max-w-xs p-2 rounded-lg bg-rose-950/80 border border-rose-800/80 text-[10px] text-rose-200 backdrop-blur-md shadow-lg flex items-center gap-1.5"><AlertCircle className="w-3.5 h-3.5 text-rose-400 shrink-0" /><span>{gpsError}</span></div>}
        {!isSecureContext && <div className="max-w-xs p-2 rounded-lg bg-amber-950/80 border border-amber-800/80 text-[10px] text-amber-200 backdrop-blur-md shadow-lg flex items-center gap-1.5"><AlertCircle className="w-3.5 h-3.5 text-amber-400 shrink-0" /><span>Note: GPS requires HTTPS or localhost.</span></div>}
      </div>

      {onOpenReportModal && (
        <div className="absolute bottom-6 right-6 z-10 pointer-events-auto">
          <button type="button" onClick={onOpenReportModal} className="flex items-center gap-2 px-4 py-3 rounded-2xl bg-gradient-to-r from-rose-600 to-amber-600 hover:from-rose-500 hover:to-amber-500 text-white font-semibold text-xs shadow-2xl shadow-rose-950/80 backdrop-blur-md transition-all active:scale-95 border border-rose-400/30">
            <ShieldAlert className="w-4 h-4" />
            <span>Report Incident</span>
          </button>
        </div>
      )}
    </div>
  );
};
