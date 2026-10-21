import React from 'react';
import { RouteItem, RouteTrafficSummary } from '@/types/routing';
import { formatDistance, formatDuration } from '@/utils/formatters';
import { Route, CheckCircle2, AlertTriangle, ShieldCheck } from 'lucide-react';
import { WeatherChip } from './WeatherChip';
import { TrafficBreakdown } from './TrafficBreakdown';

interface RouteListProps {
  routes: RouteItem[];
  selectedIndex: number;
  onSelect: (index: number) => void;
  provider: string;
  traffic?: RouteTrafficSummary | null;
}

export const RouteList: React.FC<RouteListProps> = ({
  routes,
  selectedIndex,
  onSelect,
  provider,
  traffic,
}) => {
  if (routes.length === 0) return null;

  const isFallback = provider === 'osrm-demo';
  const modelAvailable = traffic?.model_available ?? true;

  return (
    <div className="space-y-2.5">
      {/* Top Banner & Weather Chip */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        {isFallback && (
          <div className="p-2 rounded-xl bg-amber-950/40 border border-amber-800/40 flex items-center gap-2 text-amber-300 text-xs">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
            <span className="font-semibold uppercase tracking-wider text-[10px] bg-amber-500/20 px-1.5 py-0.5 rounded text-amber-300">
              fallback
            </span>
            <span className="text-[11px] text-amber-400 truncate">OSRM server</span>
          </div>
        )}
        {traffic?.weather && <WeatherChip weather={traffic.weather} />}
      </div>

      <div className="space-y-2">
        {routes.map((route, idx) => {
          const isSelected = idx === selectedIndex;
          const isRecommended = route.rank === 1 || (idx === 0 && !route.rank);
          const displayMainDuration = route.adjusted_duration_s || route.predicted_duration_s || route.duration_s;

          return (
            <button
              key={idx}
              type="button"
              onClick={() => onSelect(idx)}
              className={`w-full text-left p-3.5 rounded-2xl border transition-all flex flex-col gap-2.5 ${
                isSelected
                  ? 'bg-cyan-950/40 border-cyan-500/60 shadow-lg shadow-cyan-950/30 ring-1 ring-cyan-500/30'
                  : 'bg-slate-900/60 border-slate-800 hover:border-slate-700 hover:bg-slate-800/50'
              }`}
            >
              <div className="flex items-start justify-between gap-3 w-full">
                <div className="flex items-center gap-3">
                  <div
                    className={`w-8 h-8 rounded-xl flex items-center justify-center text-xs font-bold ${
                      isSelected ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20' : 'bg-slate-800 text-slate-400'
                    }`}
                  >
                    <Route className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="flex items-baseline gap-2">
                      <span className="text-base font-extrabold text-slate-100">
                        {formatDuration(displayMainDuration)}
                      </span>
                      <span className="text-[11px] text-slate-400">
                        ({formatDistance(route.distance_m)})
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 mt-0.5">
                      {route.steps.length} turns
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-1.5 shrink-0">
                  {isRecommended && (
                    <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                      Recommended
                    </span>
                  )}
                  {isSelected && <CheckCircle2 className="w-4 h-4 text-cyan-400 shrink-0" />}
                </div>
              </div>

              {/* Traffic and Incidents Breakdown */}
              <TrafficBreakdown route={route} modelAvailable={modelAvailable} />

              {/* Avoids Incidents Badge */}
              {route.avoids_incidents && (
                <div className="pt-0.5">
                  <span
                    data-testid="avoid-badge"
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-medium bg-emerald-500/15 border border-emerald-500/30 text-emerald-300"
                  >
                    <ShieldCheck className="w-3 h-3 text-emerald-400" />
                    <span>Avoids incidents</span>
                  </span>
                </div>
              )}

              {/* Reason Explanation */}
              {route.reason && (
                <p className="text-[11px] text-slate-300/90 leading-tight">
                  {route.reason}
                </p>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
};
