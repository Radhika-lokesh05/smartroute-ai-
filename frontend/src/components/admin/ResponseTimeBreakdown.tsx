import React from 'react';
import { MetricsSummaryResponse } from '@/types/admin';

interface ResponseTimeBreakdownProps {
  summary?: MetricsSummaryResponse;
  isLoading?: boolean;
}

export const ResponseTimeBreakdown: React.FC<ResponseTimeBreakdownProps> = ({ summary, isLoading }) => {
  const rt = summary?.dispatches?.response_times_s;

  const stages = [
    {
      label: 'Validation → Offer',
      med: rt?.validation_to_offer?.median,
      p90: rt?.validation_to_offer?.p90,
      color: 'bg-cyan-500',
    },
    {
      label: 'Offer → Accept',
      med: rt?.offer_to_accept?.median,
      p90: rt?.offer_to_accept?.p90,
      color: 'bg-indigo-500',
    },
    {
      label: 'Accept → At Scene',
      med: rt?.accept_to_at_scene?.median,
      p90: rt?.accept_to_at_scene?.p90,
      color: 'bg-amber-500',
    },
    {
      label: 'At Scene → Hospital',
      med: rt?.at_scene_to_hospital?.median,
      p90: rt?.at_scene_to_hospital?.p90,
      color: 'bg-emerald-500',
    },
  ];

  const maxVal = Math.max(...stages.map((s) => s.p90 || s.med || 0), 10);

  return (
    <div className="rounded-xl bg-slate-900 border border-slate-800 p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">
          Response Time by Stage
        </h4>
        <span className="text-[11px] font-mono text-slate-400">p50 / p90 seconds</span>
      </div>

      {isLoading ? (
        <div className="space-y-3 py-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-6 bg-slate-800 animate-pulse rounded" />
          ))}
        </div>
      ) : (
        <div className="space-y-3.5">
          {stages.map((st) => {
            const medWidth = st.med ? Math.min(100, (st.med / maxVal) * 100) : 0;
            const p90Width = st.p90 ? Math.min(100, (st.p90 / maxVal) * 100) : 0;

            return (
              <div key={st.label} className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span className="text-slate-300 font-medium">{st.label}</span>
                  <span className="font-mono text-slate-400">
                    {st.med != null ? `${st.med.toFixed(1)}s` : '—'} /{' '}
                    <span className="text-slate-200">{st.p90 != null ? `${st.p90.toFixed(1)}s` : '—'}</span>
                  </span>
                </div>
                <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden relative">
                  <div
                    className={`h-full ${st.color} opacity-40 rounded-full absolute top-0 left-0 transition-all duration-500`}
                    style={{ width: `${p90Width}%` }}
                  />
                  <div
                    className={`h-full ${st.color} rounded-full absolute top-0 left-0 transition-all duration-500`}
                    style={{ width: `${medWidth}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
