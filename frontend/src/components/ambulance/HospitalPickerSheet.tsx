import React from 'react';
import { HospitalNearbyItem } from '@/types/hospital';
import { useNearbyHospitalsQuery } from '@/hooks/useNearbyHospitalsQuery';
import { Hospital, X, Check, Loader2 } from 'lucide-react';
import { formatDuration } from '@/utils/formatters';

interface HospitalPickerSheetProps {
  isOpen: boolean;
  onClose: () => void;
  userLocation?: { lat: number; lng: number } | null;
  selectedHospitalId?: string | null;
  onSelect: (hospital: HospitalNearbyItem) => void;
  emergencyType?: string;
}

export const HospitalPickerSheet: React.FC<HospitalPickerSheetProps> = ({
  isOpen,
  onClose,
  userLocation,
  selectedHospitalId,
  onSelect,
  emergencyType = 'general',
}) => {
  const { data, isLoading } = useNearbyHospitalsQuery({
    lat: userLocation?.lat,
    lng: userLocation?.lng,
    emergencyType,
  });

  if (!isOpen) return null;

  const hospitals = data?.hospitals ? data.hospitals.slice(0, 5) : [];

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="hospital-picker-title"
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 bg-slate-950/80 backdrop-blur-sm animate-fade-in"
    >
      <div className="w-full sm:max-w-md max-h-[80vh] bg-slate-900 border border-slate-800 rounded-t-2xl sm:rounded-2xl shadow-2xl flex flex-col overflow-hidden">
        <div className="p-4 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Hospital className="w-5 h-5 text-rose-400" />
            <h3 id="hospital-picker-title" className="font-bold text-sm text-slate-100">
              Select Receiving Hospital
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-white"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-2.5">
          {isLoading ? (
            <div className="p-8 text-center flex flex-col items-center gap-2 text-slate-400">
              <Loader2 className="w-6 h-6 animate-spin text-rose-400" />
              <span className="text-xs">Fetching ranked hospitals...</span>
            </div>
          ) : hospitals.length === 0 ? (
            <p className="text-xs text-slate-400 text-center py-6">No nearby hospitals found.</p>
          ) : (
            hospitals.map((hosp) => {
              const isSelected = hosp.id === selectedHospitalId;
              return (
                <button
                  key={hosp.id}
                  type="button"
                  onClick={() => {
                    onSelect(hosp);
                    onClose();
                  }}
                  className={`w-full p-3 rounded-xl border text-left flex items-center justify-between transition-all ${
                    isSelected
                      ? 'bg-rose-950/40 border-rose-600 text-slate-100 shadow-sm'
                      : 'bg-slate-950/60 border-slate-800 text-slate-300 hover:border-slate-700'
                  }`}
                >
                  <div className="min-w-0 pr-2">
                    <span className="font-bold text-xs block truncate">{hosp.name}</span>
                    <span className="text-[11px] text-slate-400 font-mono">
                      {(hosp.distance_m / 1000).toFixed(1)} km • ETA {formatDuration(hosp.eta_s)}
                    </span>
                    <span className="text-[10px] text-amber-400 block mt-0.5">
                      {hosp.simulated_beds} Beds (Simulated)
                    </span>
                  </div>
                  {isSelected && (
                    <div className="w-6 h-6 rounded-full bg-rose-600 flex items-center justify-center shrink-0">
                      <Check className="w-4 h-4 text-white" />
                    </div>
                  )}
                </button>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};
