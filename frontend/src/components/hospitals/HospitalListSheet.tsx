import React, { useState } from 'react';
import { HospitalNearbyItem, EmergencyType } from '@/types/hospital';
import { useNearbyHospitalsQuery } from '@/hooks/useNearbyHospitalsQuery';
import { EmergencyTypeChips } from './EmergencyTypeChips';
import { HospitalCard } from './HospitalCard';
import { HospitalDisclaimerFooter } from './HospitalDisclaimerFooter';
import { X, Hospital as HospitalIcon, Loader2, Navigation, AlertCircle } from 'lucide-react';

interface HospitalListSheetProps {
  isOpen: boolean;
  onClose: () => void;
  userLocation: { lat: number; lng: number } | null;
  onSelectHospital?: (hospital: HospitalNearbyItem) => void;
  onLocateMe?: () => void;
}

export const HospitalListSheet: React.FC<HospitalListSheetProps> = ({
  isOpen,
  onClose,
  userLocation,
  onSelectHospital,
  onLocateMe,
}) => {
  const [specialty, setSpecialty] = useState<EmergencyType>('general');
  const effectiveLocation = userLocation || { lat: 12.9716, lng: 77.5946 };
  const { data, isLoading, isError, error, refetch } = useNearbyHospitalsQuery({
    lat: effectiveLocation.lat,
    lng: effectiveLocation.lng,
    emergencyType: specialty,
  });

  if (!isOpen) return null;

  const topHospitals = data?.hospitals ? data.hospitals.slice(0, 6) : [];

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="hospital-sheet-title"
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 bg-slate-950/70 backdrop-blur-sm animate-fade-in"
    >
      <div className="w-full sm:max-w-md max-h-[85vh] bg-slate-900 border border-slate-800 rounded-t-2xl sm:rounded-2xl shadow-2xl flex flex-col overflow-hidden">
        {/* Header */}
        <div className="p-4 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-rose-950/80 border border-rose-800 flex items-center justify-center">
              <HospitalIcon className="w-4 h-4 text-rose-400" />
            </div>
            <div>
              <h2 id="hospital-sheet-title" className="text-sm font-bold text-slate-100">
                Nearest Emergency Hospitals
              </h2>
              <p className="text-[11px] text-slate-400">Ranked by real-time ETA with traffic</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close emergency hospital sheet"
            className="p-1 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Specialty Filter */}
        <div className="px-4 pt-3">
          <EmergencyTypeChips selectedType={specialty} onSelect={setSpecialty} />
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto px-4 py-2 space-y-3 min-h-[220px]">
          {!userLocation && onLocateMe && (
            <div className="px-3 py-2 bg-slate-800/60 border border-slate-700/60 rounded-xl text-xs text-slate-300 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-cyan-400 shrink-0" />
                <span>Showing emergency network.</span>
              </div>
              <button
                type="button"
                onClick={onLocateMe}
                className="text-cyan-400 font-semibold hover:underline flex items-center gap-1 text-[11px]"
              >
                <Navigation className="w-3 h-3" />
                <span>Use my GPS</span>
              </button>
            </div>
          )}

          {isLoading ? (
            <div className="p-8 text-center flex flex-col items-center gap-2 text-slate-400">
              <Loader2 className="w-6 h-6 animate-spin text-rose-400" />
              <span className="text-xs">Routing and ranking top hospitals...</span>
            </div>
          ) : isError ? (
            <div className="p-6 text-center flex flex-col items-center gap-2 text-rose-300">
              <p className="text-xs">Failed to load nearby hospitals: {(error as Error)?.message || 'Service unavailable'}</p>
              <button
                type="button"
                onClick={() => refetch()}
                className="px-3 py-1 rounded bg-slate-800 text-xs font-medium hover:bg-slate-700"
              >
                Retry
              </button>
            </div>
          ) : topHospitals.length === 0 ? (
            <div className="p-8 text-center text-xs text-slate-400">
              No emergency hospitals found matching this criteria.
            </div>
          ) : (
            topHospitals.map((hosp, idx) => (
              <HospitalCard
                key={hosp.id}
                hospital={hosp}
                rank={idx + 1}
                onDirections={(h) => {
                  onSelectHospital?.(h);
                  onClose();
                }}
              />
            ))
          )}
        </div>

        {/* Permanent Footer */}
        <HospitalDisclaimerFooter emergencyNumber={data?.emergency_number} />
      </div>
    </div>
  );
};
