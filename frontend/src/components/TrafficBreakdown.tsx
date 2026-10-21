import React from 'react';
import { RouteItem } from '@/types/routing';
import { AlertCircle, TrendingUp } from 'lucide-react';

interface TrafficBreakdownProps {
  route: RouteItem;
  modelAvailable?: boolean;
}

export const TrafficBreakdown: React.FC<TrafficBreakdownProps> = ({
  route,
  modelAvailable = true,
}) => {
  const freeFlowMin = Math.max(1, Math.round(route.duration_s / 60));
  const predictedDuration = route.predicted_duration_s ?? route.duration_s;
  const trafficDiffS = Math.max(0, predictedDuration - route.duration_s);
  const trafficMin = Math.round(trafficDiffS / 60);
  const incidentMin = Math.round((route.estimated_delay_s || 0) / 60);

  const trafficFactor = route.traffic_factor || 1.0;
  const hasTrafficBadge = modelAvailable && trafficFactor > 1.05;
  const trafficPct = Math.round((trafficFactor - 1.0) * 100);

  const coverage = route.traffic_coverage;
  const showCoverageWarning = modelAvailable && coverage !== undefined && coverage < 1.0;
  const coveragePct = Math.round((coverage ?? 0) * 100);

  return (
    <div className="space-y-1.5 text-xs">
      {/* Free-flow, traffic, and incidents breakdown */}
      <div className="text-[11px] text-slate-400 font-mono">
        <span>Free-flow: {freeFlowMin} min</span>
        <span className="text-slate-600"> | </span>
        <span className={trafficMin > 0 ? 'text-amber-300' : 'text-slate-400'}>
          Traffic: +{trafficMin} min
        </span>
        <span className="text-slate-600"> | </span>
        <span className={incidentMin > 0 ? 'text-rose-300' : 'text-slate-400'}>
          Incidents: +{incidentMin} min (estimated)
        </span>
      </div>

      {/* Badges container */}
      <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
        {!modelAvailable && (
          <span
            data-testid="model-unavailable-badge"
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-medium bg-slate-800 text-slate-300 border border-slate-700"
          >
            <AlertCircle className="w-3 h-3 text-slate-400" />
            <span>Traffic model unavailable — showing free-flow times</span>
          </span>
        )}

        {hasTrafficBadge && (
          <span
            data-testid="traffic-badge"
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-semibold bg-amber-500/15 border border-amber-500/30 text-amber-300"
          >
            <TrendingUp className="w-3 h-3 text-amber-400" />
            <span>+{trafficPct}% traffic</span>
          </span>
        )}
      </div>

      {/* Coverage Disclaimer */}
      {showCoverageWarning && (
        <p
          data-testid="coverage-warning"
          className="text-[10px] text-slate-400/80 italic flex items-center gap-1 pt-0.5"
        >
          <span>Traffic modeled for {coveragePct}% of route (coverage limited to known Bengaluru corridors)</span>
        </p>
      )}
    </div>
  );
};
