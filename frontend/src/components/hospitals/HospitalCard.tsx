import React from 'react';
import { HospitalNearbyItem } from '@/types/hospital';
import { Phone, Navigation, AlertTriangle, Bed } from 'lucide-react';
import { formatDuration } from '@/utils/formatters';

interface HospitalCardProps {
  hospital: HospitalNearbyItem;
  rank: number;
  onDirections?: (hospital: HospitalNearbyItem) => void;
  showDirectionsButton?: boolean;
}

export const HospitalCard: React.FC<HospitalCardProps> = ({
  hospital,
  rank,
  onDirections,
  showDirectionsButton = true,
}) => {
  const distanceKm = (hospital.distance_m / 1000).toFixed(1);
  const etaFormatted = formatDuration(hospital.eta_s);

  return (
    <article
      aria-labelledby={`hospital-name-${hospital.id}`}
      className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 hover:border-slate-700/80 transition-all flex flex-col gap-2.5 shadow-md"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="w-5 h-5 rounded-full bg-rose-950 border border-rose-800 text-[10px] font-mono font-bold text-rose-400 flex items-center justify-center shrink-0">
            {rank}
          </span>
          <h3 id={`hospital-name-${hospital.id}`} className="font-semibold text-sm text-slate-100 leading-snug">
            {hospital.name}
          </h3>
        </div>
        <div className="text-right shrink-0">
          <div className="text-xs font-bold text-rose-400 flex items-center gap-1 justify-end">
            <span>{etaFormatted}</span>
            {hospital.eta_estimated && (
              <span className="text-[10px] font-normal text-amber-400">(estimated)</span>
            )}
          </div>
          <span className="text-[10px] text-slate-400 font-mono">{distanceKm} km</span>
        </div>
      </div>

      {hospital.address && (
        <p className="text-xs text-slate-400 line-clamp-1">{hospital.address}</p>
      )}

      {!hospital.matches_type && (
        <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-amber-950/40 border border-amber-800/40 text-[11px] text-amber-300">
          <AlertTriangle className="w-3 h-3 shrink-0" />
          <span>Does not list this specialty</span>
        </div>
      )}

      <div className="flex items-center justify-between pt-1 border-t border-slate-800/60 mt-0.5">
        {/* Beds - explicitly disclosed as simulated */}
        <div className="flex items-center gap-1.5 text-xs text-slate-300">
          <Bed className="w-3.5 h-3.5 text-slate-400" />
          <span className="font-medium">{hospital.simulated_beds} Beds</span>
          <span className="px-1.5 py-0.2 rounded text-[9px] font-mono uppercase bg-slate-800 text-amber-300 border border-amber-500/30">
            Simulated
          </span>
        </div>

        <div className="flex items-center gap-2">
          {hospital.phone ? (
            <a
              href={`tel:${hospital.phone}`}
              aria-label={`Call ${hospital.name} at ${hospital.phone}`}
              className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-emerald-950/50 hover:bg-emerald-900/60 text-emerald-400 border border-emerald-800/50 text-xs font-medium transition-colors"
            >
              <Phone className="w-3 h-3" />
              <span>Call</span>
            </a>
          ) : (
            <span className="text-[10px] text-slate-500 italic">No phone</span>
          )}

          {showDirectionsButton && onDirections && (
            <button
              type="button"
              onClick={() => onDirections(hospital)}
              aria-label={`Get directions to ${hospital.name}`}
              className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-cyan-950/60 hover:bg-cyan-900/70 text-cyan-300 border border-cyan-800/60 text-xs font-semibold transition-colors"
            >
              <Navigation className="w-3 h-3 rotate-45" />
              <span>Directions</span>
            </button>
          )}
        </div>
      </div>
    </article>
  );
};
