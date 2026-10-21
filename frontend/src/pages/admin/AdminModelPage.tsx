import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { getModelInfo } from '@/api/admin';
import { AlertCircle, Cpu, Info } from 'lucide-react';

export const AdminModelPage: React.FC = () => {
  const { data: info, isLoading } = useQuery({
    queryKey: ['admin-model-info'],
    queryFn: getModelInfo,
  });

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl flex items-center justify-between">
        <div>
          <h1 className="text-base font-bold text-white tracking-wide">MACHINE LEARNING SPECIFICATIONS</h1>
          <p className="text-xs text-slate-400">Traffic prediction model telemetry, training provenance, and error baseline</p>
        </div>
        <div className="p-2 rounded-lg bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
          <Cpu className="w-5 h-5" />
        </div>
      </div>

      {isLoading ? (
        <div className="p-8 text-center text-xs text-slate-500">Loading model telemetry...</div>
      ) : !info?.model_available ? (
        <div className="p-6 bg-amber-500/10 border border-amber-500/20 rounded-xl text-amber-300 text-xs flex items-center gap-3">
          <AlertCircle className="w-5 h-5 shrink-0" />
          <span>Model metrics artifact not currently loaded. Statistical speed fallbacks active.</span>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl space-y-2">
              <span className="text-xs font-mono uppercase text-slate-400">Model Version & Data Source</span>
              <p className="text-lg font-bold text-white font-mono">{info.model_version || 'v1.0.0'}</p>
              <p className="text-xs text-cyan-400 font-mono truncate">{info.data_source}</p>
              <p className="text-[11px] text-slate-400">Dataset: <span className="font-mono text-slate-200">{info.dataset_name}</span></p>
            </div>

            <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl space-y-2">
              <span className="text-xs font-mono uppercase text-slate-400">Training Date Range</span>
              <p className="text-lg font-bold text-white font-mono">{info.date_range}</p>
              <p className="text-xs text-slate-400">Granularity: <span className="text-emerald-400 font-mono">Daily / Corridor</span></p>
            </div>
          </div>

          <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl space-y-3">
            <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">Evaluation Metrics (Model vs Baseline)</h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
              <div className="p-3 bg-slate-800/50 rounded-lg">
                <span className="text-[10px] text-slate-400 uppercase font-mono">Model MAE</span>
                <p className="text-base font-bold text-cyan-400 font-mono">{info.model_mae?.toFixed(4) ?? '—'}</p>
              </div>
              <div className="p-3 bg-slate-800/50 rounded-lg">
                <span className="text-[10px] text-slate-400 uppercase font-mono">Baseline MAE</span>
                <p className="text-base font-bold text-slate-300 font-mono">{info.baseline_mae?.toFixed(4) ?? '—'}</p>
              </div>
              <div className="p-3 bg-slate-800/50 rounded-lg">
                <span className="text-[10px] text-slate-400 uppercase font-mono">Model R²</span>
                <p className="text-base font-bold text-purple-400 font-mono">{info.model_r2?.toFixed(4) ?? '—'}</p>
              </div>
              <div className="p-3 bg-slate-800/50 rounded-lg">
                <span className="text-[10px] text-slate-400 uppercase font-mono">Baseline R²</span>
                <p className="text-base font-bold text-slate-300 font-mono">{info.baseline_r2?.toFixed(4) ?? '—'}</p>
              </div>
            </div>
          </div>

          <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-xl flex gap-3 text-xs leading-relaxed text-slate-300">
            <Info className="w-5 h-5 text-cyan-400 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-slate-100">Dataset Limitations & Honesty Note</p>
              <p className="mt-1 text-slate-400">{info.note}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
