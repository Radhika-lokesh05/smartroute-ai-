import React from 'react';
import { ActiveAmbulanceWarning } from '@/hooks/useAmbulanceWarnings';
import { MOVE_ASIDE_INSTRUCTION } from '@/constants/trafficRules';
import { bearingToCompass, getRelativeBearing } from '@/utils/compass';
import { Siren, ArrowUp, X } from 'lucide-react';

interface AmbulanceWarningBannerProps {
  warning: ActiveAmbulanceWarning | null;
  onDismiss: () => void;
  userHeading?: number | null;
}

export const AmbulanceWarningBanner: React.FC<AmbulanceWarningBannerProps> = ({
  warning,
  onDismiss,
  userHeading,
}) => {
  if (!warning) return null;

  const distanceFormatted = Math.round(warning.distance_m);
  const compass = bearingToCompass(warning.bearing_deg);
  const arrowRotation = getRelativeBearing(warning.bearing_deg, userHeading);

  const mainText = warning.approaching
    ? `Ambulance approaching, about ${distanceFormatted}m away, ${MOVE_ASIDE_INSTRUCTION}.`
    : `Ambulance nearby, about ${distanceFormatted}m away.`;

  return (
    <aside
      role="alert"
      aria-live="assertive"
      aria-atomic="true"
      className={`w-full py-2.5 px-4 flex items-center justify-between gap-3 shadow-xl transition-all border-b ${
        warning.approaching
          ? 'bg-rose-950/95 border-rose-700 text-rose-100'
          : 'bg-amber-950/95 border-amber-700 text-amber-100'
      }`}
    >
      <div className="flex items-center gap-3 min-w-0">
        <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${
          warning.approaching ? 'bg-rose-800 text-white animate-pulse' : 'bg-amber-800 text-white'
        }`}>
          <Siren className="w-5 h-5" />
        </div>

        {/* Direction Indicator */}
        <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-black/30 border border-white/10 shrink-0 text-xs font-mono font-bold">
          <ArrowUp
            className="w-3.5 h-3.5 text-cyan-300 transition-transform duration-300"
            style={{ transform: `rotate(${arrowRotation}deg)` }}
          />
          <span className="text-[11px]">{compass}</span>
        </div>

        <p className="text-xs sm:text-sm font-semibold truncate leading-tight">
          {mainText}
        </p>
      </div>

      <button
        type="button"
        onClick={onDismiss}
        aria-label="Dismiss ambulance proximity warning"
        className="p-1 rounded-md text-white/70 hover:text-white hover:bg-white/10 transition-colors shrink-0"
      >
        <X className="w-4 h-4" />
      </button>
    </aside>
  );
};
