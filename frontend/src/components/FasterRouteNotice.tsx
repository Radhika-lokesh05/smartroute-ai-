import React from 'react';
import { Zap, X } from 'lucide-react';

export interface FasterRouteNoticeProps {
  isOpen: boolean;
  onSwitch: () => void;
  onDismiss: () => void;
  savedSeconds?: number;
}

export const FasterRouteNotice: React.FC<FasterRouteNoticeProps> = ({
  isOpen,
  onSwitch,
  onDismiss,
  savedSeconds,
}) => {
  if (!isOpen) return null;

  const savedMin = savedSeconds ? Math.max(1, Math.round(savedSeconds / 60)) : null;

  return (
    <div
      role="alert"
      className="p-3 rounded-2xl bg-gradient-to-r from-emerald-950/90 via-slate-900/90 to-cyan-950/90 border border-emerald-500/40 shadow-xl shadow-emerald-950/40 backdrop-blur-md flex items-center justify-between gap-3 animate-fade-in"
    >
      <div className="flex items-center gap-2.5 min-w-0">
        <div className="w-7 h-7 rounded-lg bg-emerald-500/20 text-emerald-400 flex items-center justify-center shrink-0">
          <Zap className="w-4 h-4" />
        </div>
        <div className="min-w-0">
          <p className="text-xs font-bold text-emerald-200 truncate">
            A faster route is available
          </p>
          <p className="text-[11px] text-emerald-400/80 truncate">
            {savedMin ? `Estimated ~${savedMin} min faster avoiding reported delays` : 'Traffic updates changed the optimal route'}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        <button
          type="button"
          onClick={onSwitch}
          className="px-3 py-1.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 text-xs font-bold shadow-md shadow-emerald-950/40 transition-all active:scale-95"
        >
          Switch
        </button>
        <button
          type="button"
          onClick={onDismiss}
          className="p-1 rounded-lg text-slate-400 hover:text-slate-200 transition-colors"
          aria-label="Dismiss notice"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};
