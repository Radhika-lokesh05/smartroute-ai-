import React from 'react';
import { IncidentType, WsEventType } from '@/types/incident';
import { formatDistance } from '@/utils/formatters';
import { AlertCircle, CheckCircle, Navigation, X } from 'lucide-react';

export interface IncidentToastItem {
  id: string; // toast ID (e.g. `${incidentId}-${eventType}`)
  incidentId: string;
  eventType: WsEventType;
  incidentType: IncidentType;
  note?: string | null;
  lat: number;
  lng: number;
  distanceM?: number | null;
}

interface IncidentToastsProps {
  toasts: IncidentToastItem[];
  onDismiss: (id: string) => void;
  onShowOnMap: (lat: number, lng: number) => void;
}

export const IncidentToasts: React.FC<IncidentToastsProps> = ({
  toasts,
  onDismiss,
  onShowOnMap,
}) => {
  // Cap at 3 visible toasts
  const visible = toasts.slice(0, 3);

  if (visible.length === 0) return null;

  return (
    <aside
      aria-live="polite"
      aria-label="Realtime Incident Alerts"
      className="fixed top-16 right-4 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none"
    >
      {visible.map((toast) => {
        const isValidated = toast.eventType === 'incident.validated';
        const title = isValidated
          ? `Verified ${toast.incidentType.toUpperCase()}`
          : `New ${toast.incidentType.toUpperCase()} Reported`;

        return (
          <div
            key={toast.id}
            role="alert"
            className="pointer-events-auto p-3 rounded-xl bg-slate-900/95 border border-slate-700 shadow-2xl backdrop-blur-md text-slate-100 flex flex-col gap-2 animate-slide-in"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-2">
                {isValidated ? (
                  <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />
                ) : (
                  <AlertCircle className="w-4 h-4 text-amber-400 shrink-0" />
                )}
                <span className="font-semibold text-xs text-slate-100">{title}</span>
              </div>
              <button
                type="button"
                onClick={() => onDismiss(toast.id)}
                className="text-slate-400 hover:text-slate-200 transition-colors p-0.5"
                title="Dismiss"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>

            {toast.note && (
              <p className="text-[11px] text-slate-300 italic line-clamp-2 pl-6">
                "{toast.note}"
              </p>
            )}

            <div className="flex items-center justify-between text-[11px] pt-1 pl-6">
              <span className="text-slate-400 font-mono">
                {toast.distanceM != null ? formatDistance(toast.distanceM) : 'Nearby'}
              </span>
              <button
                type="button"
                onClick={() => {
                  onShowOnMap(toast.lat, toast.lng);
                  onDismiss(toast.id);
                }}
                className="flex items-center gap-1 text-cyan-400 hover:text-cyan-300 font-medium text-[11px] transition-colors"
              >
                <Navigation className="w-3 h-3 rotate-45" />
                <span>Show on map</span>
              </button>
            </div>
          </div>
        );
      })}
    </aside>
  );
};
