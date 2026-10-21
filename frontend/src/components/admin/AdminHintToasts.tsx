import React from 'react';
import { AdminHintToast } from '@/hooks/useAdminHints';
import { ShieldCheck, Siren, X } from 'lucide-react';

interface AdminHintToastsProps {
  toasts: AdminHintToast[];
  onDismiss: (id: string) => void;
}

export const AdminHintToasts: React.FC<AdminHintToastsProps> = ({ toasts, onDismiss }) => {
  if (toasts.length === 0) return null;

  return (
    <div
      aria-live="polite"
      className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm pointer-events-none"
    >
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className="pointer-events-auto p-3 rounded-xl bg-slate-900/95 border border-cyan-800/80 shadow-2xl backdrop-blur-md flex items-start gap-2.5 text-xs text-slate-200 animate-slide-up"
        >
          <div className="w-6 h-6 rounded-md bg-cyan-950 border border-cyan-700/80 flex items-center justify-center shrink-0">
            {toast.type === 'prealert' ? (
              <Siren className="w-3.5 h-3.5 text-rose-400" />
            ) : (
              <ShieldCheck className="w-3.5 h-3.5 text-cyan-400" />
            )}
          </div>
          <div className="flex-1 min-w-0">
            <span className="font-bold text-slate-100 block leading-tight">{toast.title}</span>
            <p className="text-[11px] text-slate-300 mt-0.5">{toast.message}</p>
          </div>
          <button
            type="button"
            onClick={() => onDismiss(toast.id)}
            aria-label="Dismiss notification"
            className="text-slate-400 hover:text-slate-200 p-0.5"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      ))}
    </div>
  );
};
