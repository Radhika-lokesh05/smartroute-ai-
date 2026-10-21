import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Header } from '@/components/Header';
import { EmergencyTypeChips } from '@/components/hospitals/EmergencyTypeChips';
import { HospitalCard } from '@/components/hospitals/HospitalCard';
import { HospitalDisclaimerFooter } from '@/components/hospitals/HospitalDisclaimerFooter';
import { useGeolocation } from '@/hooks/useGeolocation';
import { useNearbyHospitalsQuery } from '@/hooks/useNearbyHospitalsQuery';
import { EmergencyType, HospitalNearbyItem } from '@/types/hospital';
import { Hospital as HospitalIcon, Loader2, Navigation, AlertCircle } from 'lucide-react';

export const HospitalsPage: React.FC = () => {
  const navigate = useNavigate();
  const [specialty, setSpecialty] = useState<EmergencyType>('general');
  const { location: userLocation, locateMe, isLocating } = useGeolocation();
  const effectiveLocation = userLocation || { lat: 12.9716, lng: 77.5946 };

  const { data, isLoading, isError, error, refetch } = useNearbyHospitalsQuery({
    lat: effectiveLocation.lat,
    lng: effectiveLocation.lng,
    emergencyType: specialty,
  });

  const topHospitals = data?.hospitals ? data.hospitals.slice(0, 6) : [];

  const handleDirections = (hospital: HospitalNearbyItem) => {
    // Navigate to map and pass hospital coordinates as state for automatic routing
    navigate('/', {
      state: {
        destination: {
          lat: hospital.lat,
          lng: hospital.lng,
          label: hospital.name,
        },
      },
    });
  };

  return (
    <div className="flex flex-col min-h-screen bg-slate-950 text-slate-100">
      <Header />
      <main className="flex-1 max-w-2xl w-full mx-auto p-4 sm:p-6 flex flex-col gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-rose-950 border border-rose-800 flex items-center justify-center shadow-lg shadow-rose-950/40">
            <HospitalIcon className="w-5 h-5 text-rose-400" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-slate-100">Emergency Hospital Care</h1>
            <p className="text-xs text-slate-400">Real-time dynamic hospital routing & simulated beds</p>
          </div>
        </div>

        {/* Emergency Specialty Selector */}
        <div className="bg-slate-900/60 p-3 rounded-xl border border-slate-800/80">
          <span className="block text-[11px] font-mono text-slate-400 uppercase tracking-wider mb-2">
            Select Emergency Specialty
          </span>
          <EmergencyTypeChips selectedType={specialty} onSelect={setSpecialty} />
        </div>

        {/* Main List */}
        <div className="flex-1 flex flex-col gap-3">
          {!userLocation && (
            <div className="p-3 bg-slate-900 border border-slate-800 rounded-xl flex items-center justify-between text-xs text-slate-300">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-cyan-400 shrink-0" />
                <span>Showing hospitals near Bengaluru center.</span>
              </div>
              <button
                type="button"
                onClick={locateMe}
                disabled={isLocating}
                className="px-2.5 py-1 rounded bg-cyan-950 text-cyan-300 border border-cyan-800/80 text-xs font-semibold flex items-center gap-1 hover:bg-cyan-900"
              >
                <Navigation className="w-3.5 h-3.5" />
                <span>{isLocating ? 'Locating...' : 'Use My GPS'}</span>
              </button>
            </div>
          )}

          {isLoading ? (
            <div className="p-12 text-center flex flex-col items-center gap-3 text-slate-400">
              <Loader2 className="w-8 h-8 animate-spin text-rose-400" />
              <span className="text-xs">Calculating traffic delays and routing to nearest facilities...</span>
            </div>
          ) : isError ? (
            <div className="p-8 text-center flex flex-col items-center gap-3 bg-rose-950/20 rounded-xl border border-rose-900/40 text-rose-300">
              <p className="text-xs">Unable to load hospital routes: {(error as Error)?.message || 'Service offline'}</p>
              <button
                type="button"
                onClick={() => refetch()}
                className="px-4 py-1.5 rounded-lg bg-slate-800 text-xs font-medium hover:bg-slate-700"
              >
                Retry Search
              </button>
            </div>
          ) : topHospitals.length === 0 ? (
            <div className="p-8 text-center text-xs text-slate-400 bg-slate-900/30 rounded-xl border border-slate-800">
              No emergency facilities found matching this criteria within 15 km.
            </div>
          ) : (
            <div className="space-y-3">
              {topHospitals.map((hosp, idx) => (
                <HospitalCard
                  key={hosp.id}
                  hospital={hosp}
                  rank={idx + 1}
                  onDirections={handleDirections}
                />
              ))}
            </div>
          )}
        </div>

        <div className="rounded-xl overflow-hidden border border-slate-800">
          <HospitalDisclaimerFooter emergencyNumber={data?.emergency_number} />
        </div>
      </main>
    </div>
  );
};
