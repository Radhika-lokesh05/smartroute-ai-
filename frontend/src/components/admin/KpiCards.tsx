import React from 'react';
import { CheckCircle2, Clock, ThumbsUp, Truck } from 'lucide-react';
import { MetricsSummaryResponse } from '@/types/admin';

interface KpiCardsProps {
  summary?: MetricsSummaryResponse;
  isLoading?: boolean;
}

export const KpiCards: React.FC<KpiCardsProps> = ({ summary, isLoading }) => {
  const formatRate = (rate?: number | null) => {
    if (rate === null || rate === undefined || Number.isNaN(rate)) return '0.0%';
    return `${(rate * 100).toFixed(1)}%`;
  };

  const formatSec = (val?: number | null) => {
    if (val === null || val === undefined || Number.isNaN(val)) return '—';
    return `${val.toFixed(1)}s`;
  };

  const cards = [
    {
      id: 'kpi-validation-rate',
      title: 'Validation Rate',
      value: formatRate(summary?.incidents?.validation_rate),
      subtext: `${summary?.incidents?.validated ?? 0} of ${summary?.incidents?.reported ?? 0} incidents confirmed`,
      icon: CheckCircle2,
      color: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
    },
    {
      id: 'kpi-response-time',
      title: 'Response Time (p50 / p90)',
      value: `${formatSec(summary?.dispatches?.response_times_s?.total_validation_to_at_scene?.median)} / ${formatSec(summary?.dispatches?.response_times_s?.total_validation_to_at_scene?.p90)}`,
      subtext: 'Validation to at-scene arrival',
      icon: Clock,
      color: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/20',
    },
    {
      id: 'kpi-acceptance-rate',
      title: 'Dispatch Acceptance',
      value: formatRate(summary?.dispatches?.acceptance_rate),
      subtext: `${summary?.dispatches?.accepted ?? 0} accepted / ${summary?.dispatches?.offered ?? 0} offers`,
      icon: ThumbsUp,
      color: 'text-indigo-400 bg-indigo-500/10 border-indigo-500/20',
    },
    {
      id: 'kpi-active-ambulances',
      title: 'Active Ambulances',
      value: `${summary?.ambulances?.active_now ?? 0} / ${summary?.ambulances?.total_verified ?? 0}`,
      subtext: `Availability: ${formatRate(summary?.ambulances?.average_availability)}`,
      icon: Truck,
      color: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((card) => {
        const Icon = card.icon;
        return (
          <div
            key={card.id}
            data-testid={card.id}
            className="p-4 rounded-xl bg-slate-900 border border-slate-800 flex flex-col justify-between shadow-lg"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400">{card.title}</span>
              <div className={`p-2 rounded-lg border ${card.color}`}>
                <Icon className="w-4 h-4" />
              </div>
            </div>
            <div className="mt-3">
              {isLoading ? (
                <div className="h-7 w-24 bg-slate-800 animate-pulse rounded" />
              ) : (
                <p className="text-xl font-bold font-mono text-white tracking-tight">{card.value}</p>
              )}
              <p className="text-[11px] text-slate-400 mt-1 truncate">{card.subtext}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
};
