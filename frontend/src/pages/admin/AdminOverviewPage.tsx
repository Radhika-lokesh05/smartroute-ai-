import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getMetricsHotspots, getMetricsSummary, getMetricsTimeseries } from '@/api/admin';
import { KpiCards } from '@/components/admin/KpiCards';
import { TimeSeriesChart } from '@/components/admin/TimeSeriesChart';
import { ResponseTimeBreakdown } from '@/components/admin/ResponseTimeBreakdown';
import { HotspotHeatmap } from '@/components/admin/HotspotHeatmap';
import { CsvExportButtons } from '@/components/admin/CsvExportButtons';
import { Sparkles } from 'lucide-react';

export const AdminOverviewPage: React.FC = () => {
  const [days, setDays] = useState<number>(7);
  const [origin, setOrigin] = useState<'all' | 'live' | 'simulated'>('all');

  const { data: summary, isLoading: loadingSummary } = useQuery({
    queryKey: ['admin-metrics-summary', days, origin],
    queryFn: () => getMetricsSummary(days, origin),
    refetchInterval: 30000,
  });

  const { data: timeseries, isLoading: loadingTimeseries } = useQuery({
    queryKey: ['admin-metrics-timeseries', days, origin],
    queryFn: () => getMetricsTimeseries(days, days === 1 ? 'hour' : 'day', origin),
  });

  const { data: hotspots, isLoading: loadingHotspots } = useQuery({
    queryKey: ['admin-metrics-hotspots', days, origin],
    queryFn: () => getMetricsHotspots(days, origin),
  });

  const isSimulatedActive = origin === 'simulated' || origin === 'all';

  return (
    <div className="space-y-6">
      {/* Header controls: Range selector & Origin Filter */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-slate-900 border border-slate-800 p-4 rounded-xl">
        <div className="flex items-center gap-3">
          <div>
            <h1 className="text-base font-bold text-white tracking-wide">SYSTEM PERFORMANCE</h1>
            <p className="text-xs text-slate-400">Emergency response and telemetry metrics</p>
          </div>
          {isSimulatedActive && (
            <span
              data-testid="simulated-badge"
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-purple-500/15 border border-purple-500/30 text-[11px] font-semibold text-purple-300"
            >
              <Sparkles className="w-3 h-3 text-purple-400" />
              Simulated data
            </span>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Days Selector */}
          <div className="flex bg-slate-800 p-1 rounded-lg border border-slate-700/60 text-xs font-mono">
            {[
              { label: '24h', val: 1 },
              { label: '7d', val: 7 },
              { label: '30d', val: 30 },
            ].map((opt) => (
              <button
                key={opt.val}
                onClick={() => setDays(opt.val)}
                className={`px-3 py-1 rounded-md transition ${
                  days === opt.val ? 'bg-cyan-500 text-slate-950 font-bold' : 'text-slate-400 hover:text-white'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          {/* Origin filter */}
          <div className="flex bg-slate-800 p-1 rounded-lg border border-slate-700/60 text-xs font-mono">
            {(['all', 'live', 'simulated'] as const).map((opt) => (
              <button
                key={opt}
                onClick={() => setOrigin(opt)}
                className={`px-2.5 py-1 rounded-md capitalize transition ${
                  origin === opt ? 'bg-slate-700 text-cyan-300 font-semibold' : 'text-slate-400 hover:text-white'
                }`}
              >
                {opt}
              </button>
            ))}
          </div>

          {/* CSV Export */}
          <CsvExportButtons days={days} origin={origin} />
        </div>
      </div>

      {/* KPI Cards */}
      <KpiCards summary={summary} isLoading={loadingSummary} />

      {/* Activity Timeseries & Stage Response Times */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <TimeSeriesChart points={timeseries?.points || []} isLoading={loadingTimeseries} />
        </div>
        <div className="lg:col-span-1">
          <ResponseTimeBreakdown summary={summary} isLoading={loadingSummary} />
        </div>
      </div>

      {/* Hotspots Heatmap */}
      <HotspotHeatmap cells={hotspots?.cells || []} isLoading={loadingHotspots} />
    </div>
  );
};
