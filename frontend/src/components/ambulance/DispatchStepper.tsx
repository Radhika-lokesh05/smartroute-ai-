import React, { useState } from 'react';
import { DispatchStatus } from '@/types/dispatch';
import { MapPin, Navigation, Hospital, CheckCircle, AlertTriangle } from 'lucide-react';

interface DispatchStepperProps {
  currentStatus: DispatchStatus;
  onAdvance: (nextStatus: DispatchStatus) => Promise<void>;
  onOpenHospitalPicker?: () => void;
  selectedHospitalName?: string;
  isSubmitting?: boolean;
}

const STEPS: { status: DispatchStatus; label: string; icon: React.FC<{ className?: string }> }[] = [
  { status: 'en_route_to_scene', label: 'En Route', icon: Navigation },
  { status: 'at_scene', label: 'At Scene', icon: MapPin },
  { status: 'to_hospital', label: 'To Hospital', icon: Hospital },
  { status: 'completed', label: 'Completed', icon: CheckCircle },
];

export const DispatchStepper: React.FC<DispatchStepperProps> = ({
  currentStatus,
  onAdvance,
  onOpenHospitalPicker,
  selectedHospitalName,
  isSubmitting = false,
}) => {
  const [showConfirm, setShowConfirm] = useState(false);

  const getStepIndex = (status: DispatchStatus): number => {
    switch (status) {
      case 'offered':
      case 'accepted':
      case 'en_route_to_scene':
        return 0;
      case 'at_scene':
        return 1;
      case 'to_hospital':
        return 2;
      case 'completed':
        return 3;
      default:
        return 0;
    }
  };

  const currentIndex = getStepIndex(currentStatus);

  // Compute the single next valid action
  const getNextAction = (): { nextStatus: DispatchStatus; label: string; requireConfirm?: boolean } | null => {
    switch (currentStatus) {
      case 'en_route_to_scene':
      case 'accepted':
        return { nextStatus: 'at_scene', label: 'Arrive at Scene' };
      case 'at_scene':
        return { nextStatus: 'to_hospital', label: 'Transport to Hospital' };
      case 'to_hospital':
        return { nextStatus: 'completed', label: 'Complete Mission', requireConfirm: true };
      default:
        return null;
    }
  };

  const nextAction = getNextAction();

  const handleActionClick = () => {
    if (!nextAction) return;
    if (nextAction.requireConfirm) {
      setShowConfirm(true);
    } else {
      onAdvance(nextAction.nextStatus);
    }
  };

  return (
    <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 shadow-xl flex flex-col gap-4">
      {/* Progress Steps Header */}
      <div className="flex items-center justify-between relative px-2">
        <div className="absolute left-6 right-6 top-1/2 -translate-y-1/2 h-0.5 bg-slate-800 -z-0" />
        {STEPS.map((step, idx) => {
          const Icon = step.icon;
          const isDone = idx < currentIndex;
          const isCurrent = idx === currentIndex;
          return (
            <div key={step.status} className="flex flex-col items-center gap-1.5 z-10 bg-slate-900 px-1">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center border-2 transition-all ${
                  isDone
                    ? 'bg-emerald-950 border-emerald-500 text-emerald-400'
                    : isCurrent
                    ? 'bg-cyan-950 border-cyan-400 text-cyan-300 ring-4 ring-cyan-500/20 animate-pulse'
                    : 'bg-slate-950 border-slate-800 text-slate-600'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
              </div>
              <span className={`text-[10px] font-bold ${isCurrent ? 'text-cyan-300' : isDone ? 'text-emerald-400' : 'text-slate-500'}`}>
                {step.label}
              </span>
            </div>
          );
        })}
      </div>

      {/* Selected destination hospital info when preparing for hospital leg */}
      {currentStatus === 'at_scene' && (
        <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between text-xs">
          <div>
            <span className="text-[10px] text-slate-400 uppercase font-mono block">Destination Hospital</span>
            <span className="font-bold text-slate-200">{selectedHospitalName || 'Select Hospital'}</span>
          </div>
          {onOpenHospitalPicker && (
            <button
              type="button"
              onClick={onOpenHospitalPicker}
              className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-cyan-400 border border-slate-700 text-xs font-medium"
            >
              Change
            </button>
          )}
        </div>
      )}

      {/* Single Primary Action Button */}
      {nextAction && (
        <>
          {showConfirm ? (
            <div className="p-3 rounded-xl bg-amber-950/40 border border-amber-800/80 flex flex-col gap-2.5">
              <div className="flex items-center gap-2 text-xs font-semibold text-amber-300">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>Confirm mission completion and patient handover?</span>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setShowConfirm(false)}
                  className="py-2.5 rounded-lg bg-slate-800 text-xs font-bold text-slate-300 hover:bg-slate-700"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={isSubmitting}
                  onClick={() => {
                    setShowConfirm(false);
                    onAdvance(nextAction.nextStatus);
                  }}
                  className="py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-xs font-bold text-slate-950"
                >
                  Yes, Complete
                </button>
              </div>
            </div>
          ) : (
            <button
              type="button"
              disabled={isSubmitting}
              onClick={handleActionClick}
              className="w-full h-14 rounded-xl bg-gradient-to-r from-cyan-600 to-teal-500 hover:from-cyan-500 hover:to-teal-400 active:scale-95 text-slate-950 font-black text-base flex items-center justify-center gap-2 shadow-lg shadow-cyan-950/50 transition-all disabled:opacity-50"
            >
              <span>{isSubmitting ? 'Updating...' : nextAction.label}</span>
            </button>
          )}
        </>
      )}
    </div>
  );
};
