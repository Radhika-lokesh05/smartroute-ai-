import React from 'react';

export const MapRouteLegend: React.FC = () => {
  return (
    <div className="p-2.5 rounded-xl bg-slate-900/90 border border-slate-800 text-[11px] text-slate-300 shadow-xl backdrop-blur-md flex flex-wrap items-center gap-3">
      <div className="flex items-center gap-1.5">
        <span className="w-4 h-1.5 rounded-full bg-cyan-400 inline-block shadow-sm shadow-cyan-400/50" />
        <span className="text-slate-200 font-medium">Recommended</span>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="w-4 h-1 border-t-2 border-dashed border-slate-500 inline-block" />
        <span className="text-slate-400">Alternative</span>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="w-2.5 h-2.5 rounded-full bg-amber-500 ring-2 ring-amber-400/50 animate-pulse inline-block" />
        <span className="text-amber-300 font-medium">Route Incident</span>
      </div>
    </div>
  );
};
