import React from 'react';
import { PhoneCall } from 'lucide-react';

interface HospitalDisclaimerFooterProps {
  emergencyNumber?: string;
}

export const HospitalDisclaimerFooter: React.FC<HospitalDisclaimerFooterProps> = ({
  emergencyNumber = '112',
}) => {
  return (
    <footer className="mt-auto pt-3 pb-2 px-3 border-t border-slate-800/80 bg-slate-950/80 text-[11px] text-slate-400 flex flex-col sm:flex-row items-center justify-between gap-2 text-center sm:text-left">
      <span>
        Suggestions only, not medical advice. Bed numbers are simulated.
      </span>
      <div className="flex items-center gap-1.5 shrink-0">
        <span>In an emergency call</span>
        <a
          href={`tel:${emergencyNumber}`}
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded font-mono font-bold text-rose-300 bg-rose-950/80 hover:bg-rose-900 border border-rose-700/60 transition-colors"
          aria-label={`Dial national emergency helpline ${emergencyNumber}`}
        >
          <PhoneCall className="w-2.5 h-2.5 text-rose-400" />
          <span>{emergencyNumber}</span>
        </a>
      </div>
    </footer>
  );
};
