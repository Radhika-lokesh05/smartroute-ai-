import React, { useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useAdminRealtime } from '@/hooks/useAdminRealtime';
import { forceResolveIncident } from '@/api/admin';
import { ConfirmDialog } from '@/components/admin/ConfirmDialog';
import { IncidentPublic } from '@/types/incident';
import { X } from 'lucide-react';
import { TILE_URL, TILE_ATTRIBUTION } from '@/constants/map';

const ambIcon = new L.DivIcon({
  html: '<div style="background:#8b5cf6;color:white;padding:4px;border-radius:50%;border:2px solid white;box-shadow:0 0 10px #8b5cf6">🚑</div>',
  className: '',
  iconSize: [28, 28],
});

const incIcon = new L.DivIcon({
  html: '<div style="background:#ef4444;color:white;padding:4px;border-radius:50%;border:2px solid white;box-shadow:0 0 10px #ef4444">⚠️</div>',
  className: '',
  iconSize: [28, 28],
});

export const AdminLiveMapPage: React.FC = () => {
  const { incidents, ambulances, connected } = useAdminRealtime();
  const [selectedInc, setSelectedInc] = useState<IncidentPublic | null>(null);
  const [confirmResolve, setConfirmResolve] = useState<boolean>(false);
  const [resolving, setResolving] = useState<boolean>(false);

  const handleResolve = async () => {
    if (!selectedInc) return;
    setResolving(true);
    try {
      await forceResolveIncident(selectedInc.id, 'Resolved via Admin Operations Console');
      setSelectedInc(null);
      setConfirmResolve(false);
    } finally {
      setResolving(false);
    }
  };

  return (
    <div className="h-[calc(100vh-5.5rem)] flex flex-col lg:flex-row gap-4 relative overflow-hidden">
      {/* Map Area */}
      <div className="flex-1 rounded-xl overflow-hidden border border-slate-800 bg-slate-900 relative">
        <div className="absolute top-3 left-3 z-[1000] bg-slate-900/90 border border-slate-700/80 px-3 py-1.5 rounded-lg text-xs font-mono text-slate-300 backdrop-blur-md flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${connected ? 'bg-emerald-400 animate-ping' : 'bg-red-400'}`} />
          <span>{connected ? 'Admin Live Stream' : 'Connecting stream...'}</span>
          <span className="text-slate-500">|</span>
          <span className="text-cyan-400">{incidents.length} incidents</span>
          <span className="text-purple-400">{ambulances.length} ambulances</span>
        </div>

        <MapContainer center={[12.9716, 77.5946]} zoom={12} className="h-full w-full">
          <TileLayer attribution={TILE_ATTRIBUTION} url={TILE_URL} />
          {incidents.map((inc) => (
            <Marker key={inc.id} position={[inc.lat, inc.lng]} icon={incIcon} eventHandlers={{ click: () => setSelectedInc(inc) }}>
              <Popup>
                <div className="text-xs p-1">
                  <p className="font-bold text-red-600 uppercase">{inc.type}</p>
                  <p className="text-slate-700">Status: {inc.status}</p>
                  <p className="text-slate-500">Score: {inc.trust_score.toFixed(1)}</p>
                </div>
              </Popup>
            </Marker>
          ))}
          {ambulances.map((amb) => (
            <Marker key={amb.id} position={[amb.lat, amb.lng]} icon={ambIcon}>
              <Popup>
                <div className="text-xs p-1">
                  <p className="font-bold text-purple-600">{amb.plate}</p>
                  <p className="text-slate-700">Status: {amb.status}</p>
                  <p className="text-[10px] text-slate-500">Updated: {amb.lastUpdated}</p>
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>

      {/* Side List & Drawer */}
      <div className="w-full lg:w-80 bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col h-full overflow-hidden">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300 pb-2 border-b border-slate-800">
          Citywide Active Incidents ({incidents.length})
        </h3>
        <div className="flex-1 overflow-y-auto space-y-2 mt-3 pr-1">
          {incidents.length === 0 ? (
            <div className="text-center py-10 text-xs text-slate-500">No active incidents in city</div>
          ) : (
            incidents.map((inc) => (
              <div
                key={inc.id}
                onClick={() => setSelectedInc(inc)}
                className={`p-3 rounded-lg border cursor-pointer transition ${
                  selectedInc?.id === inc.id ? 'border-cyan-500 bg-cyan-950/20' : 'border-slate-800 bg-slate-800/40 hover:bg-slate-800'
                }`}
              >
                <div className="flex justify-between items-center text-xs">
                  <span className="font-bold text-slate-200 capitalize">{inc.type}</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 font-mono">{inc.status}</span>
                </div>
                <p className="text-[11px] text-slate-400 mt-1 truncate">{inc.note || 'No description provided'}</p>
                <p className="text-[10px] text-slate-500 mt-1 font-mono">({inc.lat.toFixed(4)}, {inc.lng.toFixed(4)})</p>
              </div>
            ))
          )}
        </div>

        {/* Selected Incident Drawer */}
        {selectedInc && (
          <div className="mt-3 pt-3 border-t border-slate-800 space-y-3 bg-slate-800/60 p-3 rounded-lg">
            <div className="flex justify-between items-center">
              <span className="text-xs font-bold text-cyan-400">Incident Details</span>
              <button onClick={() => setSelectedInc(null)} className="text-slate-400 hover:text-white"><X className="w-4 h-4" /></button>
            </div>
            <div className="text-xs space-y-1 text-slate-300 font-mono">
              <p>ID: {selectedInc.id.slice(0, 8)}...</p>
              <p>Confirmations: {selectedInc.confirmations}</p>
              <p>Trust Score: {selectedInc.trust_score.toFixed(1)}</p>
            </div>
            <button
              onClick={() => setConfirmResolve(true)}
              disabled={resolving}
              className="w-full py-2 bg-red-600 hover:bg-red-500 text-white text-xs font-semibold rounded-lg transition"
            >
              Force Resolve Incident
            </button>
          </div>
        )}
      </div>

      <ConfirmDialog
        isOpen={confirmResolve}
        title="Force Resolve Incident"
        message="Are you sure you want to resolve this emergency incident? This action will immediately notify all spatial subscribers and end active routing."
        confirmLabel="Force Resolve"
        onConfirm={handleResolve}
        onCancel={() => setConfirmResolve(false)}
      />
    </div>
  );
};
