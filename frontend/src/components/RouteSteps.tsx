import React, { useState } from 'react';
import { RouteStep } from '@/types/routing';
import { formatDistance } from '@/utils/formatters';
import { ChevronDown, ChevronUp, CornerUpRight, ArrowUp, Flag } from 'lucide-react';

interface RouteStepsProps {
  steps: RouteStep[];
}

export const RouteSteps: React.FC<RouteStepsProps> = ({ steps }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!steps || steps.length === 0) return null;

  return (
    <div className="mt-3 rounded-xl border border-slate-800 bg-slate-900/70 overflow-hidden">
      <button
        type="button"
        onClick={() => setIsExpanded((prev) => !prev)}
        className="w-full px-3.5 py-2.5 flex items-center justify-between text-xs font-semibold text-slate-300 hover:text-white bg-slate-800/40 hover:bg-slate-800/70 transition-colors"
      >
        <span>Turn-by-Turn Instructions ({steps.length})</span>
        {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
      </button>

      {isExpanded && (
        <ul className="max-h-56 overflow-y-auto divide-y divide-slate-800 text-xs">
          {steps.map((step, idx) => {
            const isLast = idx === steps.length - 1;
            const isFirst = idx === 0;

            return (
              <li key={idx} className="p-2.5 flex items-start gap-2.5 hover:bg-slate-800/30 transition-colors">
                <div className="mt-0.5 text-cyan-400 shrink-0">
                  {isLast ? (
                    <Flag className="w-3.5 h-3.5 text-emerald-400" />
                  ) : isFirst ? (
                    <ArrowUp className="w-3.5 h-3.5" />
                  ) : (
                    <CornerUpRight className="w-3.5 h-3.5" />
                  )}
                </div>
                <div className="flex-1">
                  <p className="text-slate-200">{step.instruction}</p>
                  {step.distance_m > 0 && (
                    <span className="text-[10px] text-slate-500 font-mono">
                      {formatDistance(step.distance_m)}
                    </span>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
};
