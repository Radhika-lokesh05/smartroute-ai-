import React, { useState } from 'react';
import { Header } from '@/components/Header';
import { UnverifiedAmbulanceScreen } from '@/components/ambulance/UnverifiedAmbulanceScreen';
import { DispatchOfferModal } from '@/components/ambulance/DispatchOfferModal';
import { DispatchStepper } from '@/components/ambulance/DispatchStepper';
import { AmbulanceMapView } from '@/components/ambulance/AmbulanceMapView';
import { HospitalPickerSheet } from '@/components/ambulance/HospitalPickerSheet';
import { UnitStatusCard } from '@/components/ambulance/UnitStatusCard';
import { useAmbulanceProfile } from '@/hooks/useAmbulanceProfile';
import { useAmbulanceTelemetry } from '@/hooks/useAmbulanceTelemetry';
import { useAmbulanceDispatch } from '@/hooks/useAmbulanceDispatch';
import { HospitalNearbyItem } from '@/types/hospital';
import { EyeOff, Radio, AlertTriangle } from 'lucide-react';

export const AmbulanceDashboard: React.FC = () => {
  const { isVerified, status: initialStatus, isLoading: isProfileLoading, refetch } = useAmbulanceProfile();
  const [selectedHospital, setSelectedHospital] = useState<HospitalNearbyItem | null>(null);
  const [isHospitalPickerOpen, setIsHospitalPickerOpen] = useState(false);

  const {
    status, setStatusState, coords, isUpdatingStatus, isTabHidden, telemetryError, updateStatus,
  } = useAmbulanceTelemetry({ initialStatus });

  const {
    activeDispatch, incomingOffer, cancellationNotice, isLoading: isDispatchLoading,
    actionError, clearCancellationNotice, dismissOffer, acceptOffer, declineOffer, advanceStatus,
  } = useAmbulanceDispatch({
    onDispatchCompletedOrCancelled: () => setStatusState('available'),
  });

  const handleToggleOnline = async () => {
    const target = status === 'available' || status === 'busy' ? 'offline' : 'available';
    await updateStatus(target);
  };

  const handleAdvanceStep = async (nextStatus: any) => {
    await advanceStatus(nextStatus, selectedHospital?.id);
  };

  if (isProfileLoading) {
    return <div className="min-h-screen bg-slate-950 flex items-center justify-center text-slate-400">Loading vehicle profile...</div>;
  }

  if (!isVerified) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col text-slate-100">
        <Header />
        <UnverifiedAmbulanceScreen onRefresh={refetch} isRefreshing={isProfileLoading} />
      </div>
    );
  }

  const isOnline = status === 'available' || status === 'busy';

  return (
    <div className="flex flex-col h-screen w-screen bg-slate-950 text-slate-100 overflow-hidden">
      <Header />

      {isTabHidden && isOnline && (
        <div className="bg-amber-950 border-b border-amber-800 px-4 py-1.5 flex items-center gap-2 text-xs text-amber-300">
          <EyeOff className="w-3.5 h-3.5 shrink-0" />
          <span>Browser tab is hidden; background GPS may be paused by OS.</span>
        </div>
      )}

      {cancellationNotice && (
        <div className="bg-rose-950 border-b border-rose-800 px-4 py-2 flex items-center justify-between text-xs text-rose-200">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{cancellationNotice}</span>
          </div>
          <button onClick={clearCancellationNotice} className="px-2 py-0.5 rounded bg-rose-900 text-[11px] font-bold">Dismiss</button>
        </div>
      )}

      <main className="flex-1 flex flex-col md:flex-row overflow-hidden relative">
        <aside className="w-full md:w-96 lg:w-[420px] bg-slate-950/95 border-r border-slate-800 flex flex-col p-4 gap-4 z-10 shrink-0 overflow-y-auto">
          <UnitStatusCard
            status={status}
            coords={coords}
            isUpdatingStatus={isUpdatingStatus}
            onToggleOnline={handleToggleOnline}
          />

          {telemetryError && (
            <p className="text-xs text-rose-400 px-1">{telemetryError}</p>
          )}

          {actionError && (
            <p className="text-xs text-amber-400 px-1">{actionError}</p>
          )}

          {/* Active Mission Stepper */}
          {activeDispatch ? (
            <DispatchStepper
              currentStatus={activeDispatch.status}
              onAdvance={handleAdvanceStep}
              onOpenHospitalPicker={() => setIsHospitalPickerOpen(true)}
              selectedHospitalName={selectedHospital?.name}
              isSubmitting={isDispatchLoading}
            />
          ) : (
            <div className="p-8 text-center flex flex-col items-center gap-3 text-slate-500 bg-slate-900/40 rounded-2xl border border-slate-800/60">
              <Radio className={`w-8 h-8 ${isOnline ? 'text-cyan-400 animate-pulse' : 'text-slate-600'}`} />
              <p className="text-xs">
                {isOnline ? 'Standing by for incoming emergency dispatches...' : 'Unit is offline. Tap "Go Available" to receive calls.'}
              </p>
            </div>
          )}
        </aside>

        {/* Map View */}
        <section className="flex-1 h-full relative">
          <AmbulanceMapView
            ambulanceCoords={coords}
            hospitalCoords={selectedHospital ? { lat: selectedHospital.lat, lng: selectedHospital.lng } : null}
          />
        </section>
      </main>

      {/* Dispatch Offer Modal */}
      {incomingOffer && (
        <DispatchOfferModal
          offer={incomingOffer}
          onAccept={acceptOffer}
          onDecline={declineOffer}
          onExpire={dismissOffer}
          isSubmitting={isDispatchLoading}
        />
      )}

      {/* Hospital Picker Sheet */}
      <HospitalPickerSheet
        isOpen={isHospitalPickerOpen}
        onClose={() => setIsHospitalPickerOpen(false)}
        userLocation={coords}
        selectedHospitalId={selectedHospital?.id}
        onSelect={setSelectedHospital}
        emergencyType={activeDispatch?.emergency_type}
      />
    </div>
  );
};
