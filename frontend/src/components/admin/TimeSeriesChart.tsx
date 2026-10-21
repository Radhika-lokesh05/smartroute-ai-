import React, { useState } from 'react';
import { TimeSeriesPoint } from '@/types/admin';

interface TimeSeriesChartProps {
  points: TimeSeriesPoint[];
  isLoading?: boolean;
}

export const TimeSeriesChart: React.FC<TimeSeriesChartProps> = ({ points, isLoading }) => {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  if (isLoading) {
    return (
      <div className="h-64 rounded-xl bg-slate-900 border border-slate-800 p-4 flex items-center justify-center">
        <div className="w-8 h-8 rounded-full border-2 border-cyan-400 border-t-transparent animate-spin" />
      </div>
    );
  }

  if (!points || points.length === 0) {
    return (
      <div className="h-64 rounded-xl bg-slate-900 border border-slate-800 p-4 flex flex-col items-center justify-center text-slate-500">
        <p className="text-sm font-medium">No activity recorded in this period</p>
        <p className="text-xs text-slate-600 mt-1">Adjust the time filter to view historical data</p>
      </div>
    );
  }

  const maxVal = Math.max(...points.map((p) => Math.max(p.incidents, p.dispatches)), 5);
  const width = 600;
  const height = 220;
  const padX = 40;
  const padY = 30;
  const chartW = width - padX * 2;
  const chartH = height - padY * 2;

  const getX = (idx: number) => padX + (idx / Math.max(points.length - 1, 1)) * chartW;
  const getY = (val: number) => padY + chartH - (val / maxVal) * chartH;

  const incPath = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${getX(i)} ${getY(p.incidents)}`).join(' ');
  const dispPath = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${getX(i)} ${getY(p.dispatches)}`).join(' ');

  return (
    <div className="rounded-xl bg-slate-900 border border-slate-800 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">Activity Over Time</h4>
        <div className="flex items-center gap-4 text-xs font-mono">
          <div className="flex items-center gap-1.5 text-cyan-400">
            <span className="w-2.5 h-0.5 bg-cyan-400 rounded" />
            <span>Incidents</span>
          </div>
          <div className="flex items-center gap-1.5 text-purple-400">
            <span className="w-2.5 h-0.5 bg-purple-400 rounded" />
            <span>Dispatches</span>
          </div>
        </div>
      </div>

      <div className="relative w-full overflow-hidden">
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-56 select-none">
          {/* Horizontal grid lines */}
          {[0, 0.5, 1].map((ratio) => {
            const y = padY + chartH * (1 - ratio);
            return (
              <g key={ratio}>
                <line x1={padX} y1={y} x2={width - padX} y2={y} stroke="#1e293b" strokeDasharray="3 3" />
                <text x={padX - 8} y={y + 3} fill="#64748b" fontSize="10" textAnchor="end" fontFamily="monospace">
                  {Math.round(maxVal * ratio)}
                </text>
              </g>
            );
          })}

          {/* Paths */}
          <path d={incPath} fill="none" stroke="#22d3ee" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
          <path d={dispPath} fill="none" stroke="#c084fc" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />

          {/* Interactive Points */}
          {points.map((p, i) => (
            <g key={i} onMouseEnter={() => setHoverIndex(i)} onMouseLeave={() => setHoverIndex(null)}>
              <circle cx={getX(i)} cy={getY(p.incidents)} r={hoverIndex === i ? 5 : 3} fill="#22d3ee" className="transition-all" />
              <circle cx={getX(i)} cy={getY(p.dispatches)} r={hoverIndex === i ? 5 : 3} fill="#c084fc" className="transition-all" />
              <line x1={getX(i)} y1={padY} x2={getX(i)} y2={height - padY} stroke="#334155" strokeWidth="1" opacity={hoverIndex === i ? 0.8 : 0} />
            </g>
          ))}
        </svg>

        {hoverIndex !== null && points[hoverIndex] && (
          <div className="absolute top-2 right-2 bg-slate-800/90 border border-slate-700 p-2 rounded-lg text-[11px] font-mono text-slate-200 pointer-events-none shadow-lg">
            <div>{new Date(points[hoverIndex].timestamp).toLocaleDateString()}</div>
            <div className="text-cyan-400">Incidents: {points[hoverIndex].incidents}</div>
            <div className="text-purple-400">Dispatches: {points[hoverIndex].dispatches}</div>
          </div>
        )}
      </div>
    </div>
  );
};
