import React from 'react';
import { ShieldCheck } from 'lucide-react';

export interface RerouteBannerProps {
  rerouted?: boolean;
  incidentsCount?: number;
}

export const RerouteBanner: React.FC<RerouteBannerProps> = ({
  rerouted,
  incidentsCount = 1,
}) => {
  if (!rerouted) return null;

  const count = incidentsCount > 0 ? incidentsCount : 1;
  const label = count === 1 ? 'incident' : 'incidents';

  return (
    <div
      role="status"
      className="p-3 rounded-2xl bg-cyan-950/60 border border-cyan-500/40 shadow-lg shadow-cyan-950/30 flex items-center gap-2.5 text-cyan-200"
    >
      <div className="w-6 h-6 rounded-lg bg-cyan-500/20 text-cyan-400 flex items-center justify-center shrink-0">
        <ShieldCheck className="w-4 h-4" />
      </div>
      <div className="text-xs font-semibold">
        <span>Recommended route avoids {count} {label}</span>
      </div>
    </div>
  );
};
