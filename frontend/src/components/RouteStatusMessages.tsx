import React from 'react';
import { Loader2, AlertCircle, Clock, WifiOff, ServerCrash } from 'lucide-react';

interface RouteStatusProps {
  isLoading: boolean;
  isError: boolean;
  error?: any;
  onRetry?: () => void;
}

export const RouteStatusMessages: React.FC<RouteStatusProps> = ({
  isLoading,
  isError,
  error,
  onRetry,
}) => {
  if (isLoading) {
    return (
      <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800 flex items-center justify-center gap-3">
        <Loader2 className="w-5 h-5 text-cyan-400 animate-spin" />
        <span className="text-xs font-medium text-slate-300">
          Calculating fastest routes & alternatives...
        </span>
      </div>
    );
  }

  if (!isError || !error) return null;

  const status = error.response?.status;
  const isOffline = !window.navigator.onLine || error.code === 'ERR_NETWORK';

  if (isOffline) {
    return (
      <div className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-700 text-slate-300 text-xs flex items-start gap-2.5">
        <WifiOff className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
        <div>
          <p className="font-semibold text-slate-200">You are currently offline</p>
          <p className="text-[11px] text-slate-400 mt-0.5">Please check your internet connection and try again.</p>
        </div>
      </div>
    );
  }

  if (status === 404) {
    return (
      <div className="p-3.5 rounded-xl bg-amber-950/30 border border-amber-800/40 text-amber-300 text-xs flex items-start gap-2.5">
        <AlertCircle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
        <div>
          <p className="font-semibold text-amber-200">No route found</p>
          <p className="text-[11px] text-amber-400/90 mt-0.5">
            Unable to connect origin and destination via road network. Try selecting closer accessible points.
          </p>
        </div>
      </div>
    );
  }

  if (status === 429) {
    return (
      <div className="p-3.5 rounded-xl bg-amber-950/30 border border-amber-800/40 text-amber-300 text-xs flex items-start gap-2.5">
        <Clock className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
        <div>
          <p className="font-semibold text-amber-200">Rate limit reached (60 req/min)</p>
          <p className="text-[11px] text-amber-400/90 mt-0.5">
            You have exceeded the route calculation rate limit. Please wait a few seconds before retrying.
          </p>
          {onRetry && (
            <button
              onClick={onRetry}
              className="mt-2 px-2.5 py-1 rounded bg-amber-900/40 hover:bg-amber-900/70 border border-amber-700/50 text-[11px] font-medium text-amber-200"
            >
              Retry Now
            </button>
          )}
        </div>
      </div>
    );
  }

  // 502/503 or generic
  return (
    <div className="p-3.5 rounded-xl bg-rose-950/30 border border-rose-800/40 text-rose-300 text-xs flex items-start gap-2.5">
      <ServerCrash className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
      <div>
        <p className="font-semibold text-rose-200">Routing service unavailable</p>
        <p className="text-[11px] text-rose-400/90 mt-0.5">
          {error.response?.data?.detail || 'Upstream navigation service is temporarily down.'}
        </p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="mt-2 px-2.5 py-1 rounded bg-rose-900/40 hover:bg-rose-900/70 border border-rose-700/50 text-[11px] font-medium text-rose-200"
          >
            Retry Request
          </button>
        )}
      </div>
    </div>
  );
};
