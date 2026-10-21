import React, { useEffect } from 'react';
import L from 'leaflet';
import { MapContainer, TileLayer, Marker, Polyline, Circle, useMap } from 'react-leaflet';
import { LeafletCoord } from '@/utils/coordinates';
import { userLocationIcon, destinationIcon } from '@/utils/leafletIcons';
import { TILE_URL, TILE_ATTRIBUTION } from '@/constants/map';

interface AmbulanceMapViewProps {
  ambulanceCoords?: { lat: number; lng: number; accuracy?: number } | null;
  sceneCoords?: { lat: number; lng: number } | null;
  hospitalCoords?: { lat: number; lng: number } | null;
  leg1Coords?: LeafletCoord[]; // Ambulance -> Scene
  leg2Coords?: LeafletCoord[]; // Scene -> Hospital
}

const DEFAULT_CENTER: LeafletCoord = [12.9716, 77.5946];

function FitController({
  coords,
}: {
  coords: LeafletCoord[];
}) {
  const map = useMap();
  useEffect(() => {
    if (coords.length >= 2) {
      map.fitBounds(L.latLngBounds(coords), { padding: [50, 50], maxZoom: 16 });
    } else if (coords.length === 1) {
      map.setView(coords[0], 15);
    }
  }, [map, coords]);
  return null;
}

export const AmbulanceMapView: React.FC<AmbulanceMapViewProps> = ({
  ambulanceCoords,
  sceneCoords,
  hospitalCoords,
  leg1Coords = [],
  leg2Coords = [],
}) => {
  const allPoints: LeafletCoord[] = [];
  if (ambulanceCoords) allPoints.push([ambulanceCoords.lat, ambulanceCoords.lng]);
  if (sceneCoords) allPoints.push([sceneCoords.lat, sceneCoords.lng]);
  if (hospitalCoords) allPoints.push([hospitalCoords.lat, hospitalCoords.lng]);

  const defaultLeg1: LeafletCoord[] =
    ambulanceCoords && sceneCoords
      ? [[ambulanceCoords.lat, ambulanceCoords.lng], [sceneCoords.lat, sceneCoords.lng]]
      : [];

  const defaultLeg2: LeafletCoord[] =
    sceneCoords && hospitalCoords
      ? [[sceneCoords.lat, sceneCoords.lng], [hospitalCoords.lat, hospitalCoords.lng]]
      : [];

  const finalLeg1 = leg1Coords.length > 0 ? leg1Coords : defaultLeg1;
  const finalLeg2 = leg2Coords.length > 0 ? leg2Coords : defaultLeg2;

  return (
    <div className="relative w-full h-full min-h-[300px]">
      <MapContainer
        center={ambulanceCoords ? [ambulanceCoords.lat, ambulanceCoords.lng] : DEFAULT_CENTER}
        zoom={14}
        scrollWheelZoom={true}
        className="w-full h-full z-0 bg-slate-950"
      >
        <TileLayer
          attribution={TILE_ATTRIBUTION}
          url={TILE_URL}
          className="dark-tiles"
        />
        <FitController coords={allPoints} />

        {/* Ambulance GPS location */}
        {ambulanceCoords && (
          <>
            <Circle
              center={[ambulanceCoords.lat, ambulanceCoords.lng]}
              radius={ambulanceCoords.accuracy || 20}
              pathOptions={{ color: '#06B6D4', fillColor: '#06B6D4', fillOpacity: 0.15, weight: 1.5 }}
            />
            <Marker position={[ambulanceCoords.lat, ambulanceCoords.lng]} icon={userLocationIcon} />
          </>
        )}

        {/* Scene Marker */}
        {sceneCoords && (
          <Marker position={[sceneCoords.lat, sceneCoords.lng]} icon={destinationIcon} />
        )}

        {/* Hospital Marker */}
        {hospitalCoords && (
          <Marker position={[hospitalCoords.lat, hospitalCoords.lng]} icon={destinationIcon} />
        )}

        {/* Leg 1: Ambulance to Scene (Cyan) */}
        {finalLeg1.length >= 2 && (
          <Polyline
            positions={finalLeg1}
            pathOptions={{ color: '#06B6D4', weight: 6, opacity: 0.9 }}
          />
        )}

        {/* Leg 2: Scene to Hospital (Emerald) */}
        {finalLeg2.length >= 2 && (
          <Polyline
            positions={finalLeg2}
            pathOptions={{ color: '#10B981', weight: 6, opacity: 0.9, dashArray: '6, 6' }}
          />
        )}
      </MapContainer>

      {/* Map Leg Color Indicator */}
      <div className="absolute top-4 left-4 z-10 p-2.5 rounded-xl bg-slate-900/90 border border-slate-800 shadow-xl backdrop-blur-md text-xs space-y-1">
        <div className="flex items-center gap-2">
          <span className="w-3 h-1 bg-cyan-400 rounded-full" />
          <span className="text-slate-300">Leg 1: To Scene</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-3 h-1 bg-emerald-400 rounded-full" />
          <span className="text-slate-300">Leg 2: To Hospital</span>
        </div>
      </div>
    </div>
  );
};
