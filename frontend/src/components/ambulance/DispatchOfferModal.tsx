import React, { useState, useEffect } from 'react';
import { DispatchOfferData } from '@/types/dispatch';
import { Siren, Clock, MapPin, Volume2, VolumeX, CheckCircle2, XCircle } from 'lucide-react';
import { formatDuration } from '@/utils/formatters';

interface DispatchOfferModalProps {
  offer: DispatchOfferData;
  onAccept: (dispatchId: string) => Promise<any>;
  onDecline: (dispatchId: string) => Promise<any>;
  onExpire: () => void;
  isSubmitting?: boolean;
}

export const DispatchOfferModal: React.FC<DispatchOfferModalProps> = ({
  offer,
  onAccept,
  onDecline,
  onExpire,
  isSubmitting = false,
}) => {
  const [secondsRemaining, setSecondsRemaining] = useState<number>(offer.expires_in_s || 60);
  const [isSoundEnabled, setIsSoundEnabled] = useState(false); // OFF by default, no autoplay

  useEffect(() => {
    const timer = setInterval(() => {
      setSecondsRemaining((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          onExpire();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [onExpire]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="offer-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/90 backdrop-blur-md animate-fade-in"
    >
      <div className="w-full max-w-lg bg-slate-900 border-2 border-rose-600/80 rounded-2xl shadow-2xl p-5 sm:p-6 flex flex-col gap-5 text-slate-100">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-rose-950 border border-rose-700 flex items-center justify-center animate-bounce">
              <Siren className="w-6 h-6 text-rose-400" />
            </div>
            <div>
              <h2 id="offer-title" className="text-base sm:text-lg font-bold text-rose-300">
                Incoming Emergency Dispatch
              </h2>
              <span className="text-xs text-slate-400">Immediate response required</span>
            </div>
          </div>

          <button
            type="button"
            onClick={() => setIsSoundEnabled((p) => !p)}
            title={isSoundEnabled ? 'Mute alert chime' : 'Enable alert chime'}
            className="p-2 rounded-lg bg-slate-800 text-slate-300 hover:text-white border border-slate-700"
          >
            {isSoundEnabled ? <Volume2 className="w-4 h-4 text-cyan-400" /> : <VolumeX className="w-4 h-4 text-slate-400" />}
          </button>
        </div>

        {/* Countdown Timer */}
        <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <Clock className="w-4 h-4 text-amber-400" />
            <span>Time to respond</span>
          </div>
          <span className={`font-mono text-xl font-bold ${secondsRemaining <= 15 ? 'text-rose-400 animate-pulse' : 'text-amber-300'}`}>
            00:{secondsRemaining.toString().padStart(2, '0')}
          </span>
        </div>

        {/* Dispatch Metrics */}
        <div className="grid grid-cols-2 gap-3">
          <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80">
            <span className="text-[10px] font-mono uppercase text-slate-400">Incident Category</span>
            <p className="font-bold text-sm text-slate-100 uppercase tracking-wide mt-0.5">
              {offer.emergency_type}
            </p>
          </div>
          <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80">
            <span className="text-[10px] font-mono uppercase text-slate-400">Estimated Drive ETA</span>
            <p className="font-bold text-sm text-rose-400 mt-0.5">
              {formatDuration(offer.eta_to_scene_s)}
            </p>
          </div>
        </div>

        {/* Coordinates preview */}
        <div className="flex items-center gap-2 text-xs text-slate-400 p-2.5 rounded-lg bg-slate-950/40 border border-slate-800/60">
          <MapPin className="w-4 h-4 text-cyan-400 shrink-0" />
          <span className="truncate">Scene: {offer.incident_lat.toFixed(4)}, {offer.incident_lng.toFixed(4)}</span>
        </div>

        {/* Action Buttons: Mobile-first large touch targets */}
        <div className="grid grid-cols-2 gap-3 pt-2">
          <button
            type="button"
            disabled={isSubmitting}
            onClick={() => onDecline(offer.dispatch_id)}
            className="h-14 rounded-xl bg-slate-800 hover:bg-slate-700 active:scale-95 text-slate-200 border border-slate-700 font-bold text-base flex items-center justify-center gap-2 transition-all disabled:opacity-50"
          >
            <XCircle className="w-5 h-5 text-rose-400" />
            <span>Decline</span>
          </button>

          <button
            type="button"
            disabled={isSubmitting}
            onClick={() => onAccept(offer.dispatch_id)}
            className="h-14 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 hover:to-teal-400 active:scale-95 text-slate-950 font-black text-base flex items-center justify-center gap-2 shadow-lg shadow-emerald-950/50 transition-all disabled:opacity-50"
          >
            <CheckCircle2 className="w-5 h-5" />
            <span>{isSubmitting ? 'Accepting...' : 'Accept Call'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
