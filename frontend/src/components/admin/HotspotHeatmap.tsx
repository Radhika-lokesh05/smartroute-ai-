import React from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet';
import { HotspotCell } from '@/types/admin';
import { TILE_URL, TILE_ATTRIBUTION } from '@/constants/map';

interface HotspotHeatmapProps {
  cells: HotspotCell[];
  isLoading?: boolean;
}

export const HotspotHeatmap: React.FC<HotspotHeatmapProps> = ({ cells, isLoading }) => {
  const defaultCenter: [number, number] = [12.9716, 77.5946];

  const getColor = (count: number) => {
    if (count >= 10) return '#ef4444'; // Red
    if (count >= 5) return '#f97316';  // Orange
    if (count >= 3) return '#eab308';  // Yellow
    return '#06b6d4';                 // Cyan
  };

  return (
    <div className="rounded-xl bg-slate-900 border border-slate-800 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h4 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">
            Incident Hotspots (250m Grid)
          </h4>
          <p className="text-[11px] text-slate-400">Spatial density clusters</p>
        </div>
        <div className="flex items-center gap-3 text-[11px] font-mono text-slate-400">
          <div className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-500 inline-block" /> Low
          </div>
          <div className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-500 inline-block" /> Med
          </div>
          <div className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-full bg-red-500 inline-block" /> High
          </div>
        </div>
      </div>

      <div className="h-72 w-full rounded-lg overflow-hidden border border-slate-800 relative">
        {isLoading && (
          <div className="absolute inset-0 z-10 bg-slate-900/70 backdrop-blur-sm flex items-center justify-center">
            <div className="w-6 h-6 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
          </div>
        )}
        <MapContainer
          center={defaultCenter}
          zoom={12}
          scrollWheelZoom={false}
          className="h-full w-full bg-slate-950"
        >
          <TileLayer
            attribution={TILE_ATTRIBUTION}
            url={TILE_URL}
          />
          {cells.map((cell, idx) => {
            const radius = Math.min(26, Math.max(6, Math.sqrt(cell.count) * 4));
            const color = getColor(cell.count);

            return (
              <CircleMarker
                key={`${cell.lat}-${cell.lng}-${idx}`}
                center={[cell.lat, cell.lng]}
                radius={radius}
                pathOptions={{
                  color,
                  fillColor: color,
                  fillOpacity: 0.65,
                  weight: 1.5,
                }}
              >
                <Popup>
                  <div className="text-xs p-1">
                    <p className="font-bold text-slate-900">Hotspot Cell</p>
                    <p className="text-slate-700">Count: <span className="font-mono font-semibold">{cell.count}</span></p>
                    <p className="text-slate-700 capitalize">Type: <span className="font-semibold">{cell.top_type}</span></p>
                    <p className="text-[10px] text-slate-500 mt-1">({cell.lat.toFixed(4)}, {cell.lng.toFixed(4)})</p>
                  </div>
                </Popup>
              </CircleMarker>
            );
          })}
        </MapContainer>
      </div>
    </div>
  );
};
