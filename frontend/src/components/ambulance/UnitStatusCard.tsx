import React from 'react';
import { Power } from 'lucide-react';
import { AmbulanceStatus } from '@/types/dispatch';
import { TelemetryCoords } from '@/hooks/useAmbulanceTelemetry';

interface UnitStatusCardProps {
  status: AmbulanceStatus;
  coords: TelemetryCoords | null;
  isUpdatingStatus: boolean;
  onToggleOnline: () => void;
}

export const UnitStatusCard: React.FC<UnitStatusCardProps> = ({
  status,
  coords,
  isUpdatingStatus,
  onToggleOnline,
}) => {
  const isOnline = status === 'available' || status === 'busy';

  return (
    <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-between shadow-lg">
      <div>
        <span className="text-[10px] font-mono uppercase text-slate-400 block">Unit Telemetry</span>
        <div className="flex items-center gap-2 mt-0.5">
          <span className={`w-2.5 h-2.5 rounded-full ${isOnline ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'}`} />
          <span className="font-bold text-sm capitalize text-slate-100">{status}</span>
        </div>
        {coords && (
          <span className="text-[10px] text-slate-400 font-mono block mt-0.5">
            GPS ±{Math.round(coords.accuracy)}m
          </span>
        )}
      </div>

      <button
        type="button"
        disabled={isUpdatingStatus || status === 'busy'}
        onClick={onToggleOnline}
        className={`h-12 px-5 rounded-xl font-bold text-xs flex items-center gap-2 transition-all active:scale-95 disabled:opacity-50 ${
          isOnline
            ? 'bg-rose-950 hover:bg-rose-900 text-rose-300 border border-rose-800'
            : 'bg-emerald-950 hover:bg-emerald-900 text-emerald-300 border border-emerald-800'
        }`}
      >
        <Power className="w-4 h-4" />
        <span>{isUpdatingStatus ? 'Switching...' : isOnline ? 'Go Offline' : 'Go Available'}</span>
      </button>
    </div>
  );
};
