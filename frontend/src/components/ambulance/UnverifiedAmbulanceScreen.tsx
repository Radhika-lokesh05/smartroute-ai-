import React from 'react';
import { ShieldAlert, RefreshCw } from 'lucide-react';

interface UnverifiedAmbulanceScreenProps {
  plateNumber?: string;
  onRefresh: () => void;
  isRefreshing?: boolean;
}

export const UnverifiedAmbulanceScreen: React.FC<UnverifiedAmbulanceScreenProps> = ({
  plateNumber,
  onRefresh,
  isRefreshing = false,
}) => {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-6 text-center max-w-md mx-auto">
      <div className="w-16 h-16 rounded-2xl bg-amber-950/70 border border-amber-800/80 flex items-center justify-center mb-4 shadow-xl shadow-amber-950/40">
        <ShieldAlert className="w-8 h-8 text-amber-400" />
      </div>

      <h2 className="text-xl font-bold text-slate-100 mb-2">
        Awaiting Admin Verification
      </h2>

      <p className="text-sm text-slate-400 mb-4 leading-relaxed">
        Your vehicle registration {plateNumber ? <strong className="text-slate-200 font-mono">({plateNumber})</strong> : null} is pending verification by emergency dispatch authorities.
      </p>

      <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-400 text-left mb-6 w-full space-y-2">
        <p className="font-semibold text-slate-300">Security Requirement:</p>
        <p>• Unverified ambulances cannot broadcast live telemetry or accept dispatches.</p>
        <p>• Once approved by a system administrator, your console will activate automatically.</p>
      </div>

      <button
        type="button"
        onClick={onRefresh}
        disabled={isRefreshing}
        className="px-5 py-2.5 rounded-xl bg-cyan-950 hover:bg-cyan-900 text-cyan-300 border border-cyan-800 font-semibold text-sm flex items-center gap-2 transition-colors disabled:opacity-50"
      >
        <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
        <span>{isRefreshing ? 'Checking Status...' : 'Re-check Verification'}</span>
      </button>
    </div>
  );
};
