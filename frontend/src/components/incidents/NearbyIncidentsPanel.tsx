import React from 'react';
import { Incident } from '@/types/incident';
import { formatCountdownSeconds, formatDistance } from '@/utils/formatters';
import { ShieldCheck, Clock, MapPin, X, Car, Construction, AlertTriangle, CheckCircle } from 'lucide-react';

interface NearbyIncidentsPanelProps {
  isOpen: boolean;
  onClose: () => void;
  incidents: Incident[];
  onSelectIncident: (incident: Incident) => void;
  isLoading: boolean;
}

export const NearbyIncidentsPanel: React.FC<NearbyIncidentsPanelProps> = ({
  isOpen,
  onClose,
  incidents,
  onSelectIncident,
  isLoading,
}) => {
  if (!isOpen) return null;

  const getIcon = (type: string) => {
    switch (type) {
      case 'accident':
        return <Car className="w-4 h-4 text-rose-400" />;
      case 'blockage':
        return <Construction className="w-4 h-4 text-amber-400" />;
      default:
        return <AlertTriangle className="w-4 h-4 text-yellow-400" />;
    }
  };

  return (
    <div className="absolute top-0 right-0 bottom-0 z-30 w-full sm:w-80 bg-slate-900/95 border-l border-slate-800 shadow-2xl backdrop-blur-md flex flex-col animate-slide-left">
      <div className="p-4 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-5 h-5 text-cyan-400" />
          <h3 className="font-semibold text-sm text-slate-100">Nearby Incidents</h3>
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded-full bg-slate-800 text-slate-300">
            {incidents.length}
          </span>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="p-1 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-2.5">
        {isLoading ? (
          <div className="py-12 text-center text-xs text-slate-400">Loading incidents...</div>
        ) : incidents.length === 0 ? (
          <div className="py-12 px-4 text-center text-xs text-slate-400">
            <CheckCircle className="w-8 h-8 text-emerald-400/60 mx-auto mb-2" />
            <p className="font-medium text-slate-300">No active incidents</p>
            <p className="text-[11px] text-slate-500 mt-1">Roads in your area are currently reported clear.</p>
          </div>
        ) : (
          incidents.map((inc) => (
            <div
              key={inc.id}
              onClick={() => onSelectIncident(inc)}
              className="p-3 rounded-xl bg-slate-950/70 hover:bg-slate-800/80 border border-slate-800 hover:border-slate-700 transition-all cursor-pointer flex flex-col gap-1.5"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  {getIcon(inc.incident_type)}
                  <span className="font-semibold text-xs capitalize text-slate-200">
                    {inc.incident_type}
                  </span>
                </div>
                <span
                  className={`text-[9px] uppercase font-mono px-1.5 py-0.5 rounded ${
                    inc.status === 'validated'
                      ? 'bg-emerald-950 text-emerald-300 border border-emerald-800/60'
                      : 'bg-amber-950 text-amber-300 border border-amber-800/60'
                  }`}
                >
                  {inc.status}
                </span>
              </div>

              {inc.note && (
                <p className="text-[11px] text-slate-300 line-clamp-2 italic">
                  "{inc.note}"
                </p>
              )}

              <div className="flex items-center justify-between text-[10px] text-slate-400 pt-1 border-t border-slate-800/60">
                <div className="flex items-center gap-1 font-mono">
                  <MapPin className="w-3 h-3 text-cyan-400" />
                  <span>{inc.distance_m != null ? formatDistance(inc.distance_m) : 'Nearby'}</span>
                </div>
                <div className="flex items-center gap-1 font-mono">
                  <Clock className="w-3 h-3 text-slate-400" />
                  <span>{formatCountdownSeconds(inc.seconds_remaining)}</span>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
