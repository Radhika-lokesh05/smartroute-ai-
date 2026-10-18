import React from 'react';
import { 
  Activity, 
  CheckCircle2, 
  AlertTriangle, 
  Database, 
  Server, 
  RefreshCw, 
  ExternalLink 
} from 'lucide-react';
import { HealthResponse } from '@/types/health';
import { API_BASE_URL } from '@/api/client';

interface StatusCardProps {
  isLoading: boolean;
  isError: boolean;
  data?: HealthResponse;
  error?: Error | null;
  onRefresh: () => void;
  isFetching: boolean;
}

export const StatusCard: React.FC<StatusCardProps> = ({
  isLoading,
  isError,
  data,
  error,
  onRefresh,
  isFetching,
}) => {
  const isConnected = !isError && !isLoading && data?.status === 'ok';
  const isDbConnected = data?.database === 'connected';

  return (
    <div className="w-full max-w-xl mx-auto transition-all duration-300">
      <div
        className={`relative overflow-hidden rounded-2xl p-6 sm:p-8 backdrop-blur-xl border transition-all duration-500 shadow-2xl ${
          isConnected
            ? 'bg-slate-900/80 border-cyan-500/30 shadow-cyan-950/40'
            : isError
            ? 'bg-slate-900/80 border-rose-500/30 shadow-rose-950/30'
            : 'bg-slate-900/80 border-slate-700/40 shadow-black/50'
        }`}
      >
        {/* Glow ambient background effect */}
        <div
          className={`absolute -top-24 -right-24 w-48 h-48 rounded-full blur-3xl pointer-events-none transition-colors duration-700 ${
            isConnected
              ? 'bg-cyan-500/15'
              : isError
              ? 'bg-rose-500/15'
              : 'bg-amber-500/10'
          }`}
        />

        {/* Header with Title and Refresh */}
        <div className="flex items-center justify-between gap-4 mb-6 relative z-10">
          <div className="flex items-center gap-3">
            <div
              className={`p-2.5 rounded-xl border ${
                isConnected
                  ? 'bg-cyan-500/10 border-cyan-500/20 text-cyan-400'
                  : isError
                  ? 'bg-rose-500/10 border-rose-500/20 text-rose-400'
                  : 'bg-amber-500/10 border-amber-500/20 text-amber-400'
              }`}
            >
              <Activity className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <h2 className="text-sm font-semibold tracking-wider uppercase text-slate-400">
                System Telemetry
              </h2>
              <p className="text-xs text-slate-500">FastAPI Async Core</p>
            </div>
          </div>

          <button
            id="refresh-health-btn"
            onClick={onRefresh}
            disabled={isFetching}
            title="Refresh status"
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-300 bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700/50 rounded-lg transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin text-cyan-400' : ''}`} />
            <span>Check</span>
          </button>
        </div>

        {/* Primary Status Banner */}
        <div className="mb-6 relative z-10">
          {isLoading ? (
            <div className="flex items-center gap-3 p-4 rounded-xl bg-slate-800/50 border border-slate-700/50 animate-pulse">
              <div className="w-4 h-4 rounded-full bg-slate-600 animate-ping" />
              <span className="text-base font-medium text-slate-300">Checking backend connectivity...</span>
            </div>
          ) : isConnected ? (
            <div className="flex items-center justify-between p-4 rounded-xl bg-emerald-950/30 border border-emerald-500/30 text-emerald-300">
              <div className="flex items-center gap-3">
                <span className="relative flex h-3.5 w-3.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-emerald-500" />
                </span>
                <span className="text-base sm:text-lg font-semibold tracking-wide text-emerald-200">
                  Backend connected
                </span>
              </div>
              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
            </div>
          ) : (
            <div className="flex items-center justify-between p-4 rounded-xl bg-rose-950/30 border border-rose-500/30 text-rose-300">
              <div className="flex items-center gap-3">
                <span className="relative flex h-3.5 w-3.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-rose-500" />
                </span>
                <span className="text-base sm:text-lg font-semibold tracking-wide text-rose-200">
                  Backend offline
                </span>
              </div>
              <AlertTriangle className="w-5 h-5 text-rose-400" />
            </div>
          )}
        </div>

        {/* Detailed Metrics */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 relative z-10">
          {/* Target URL */}
          <div className="p-3.5 rounded-xl bg-slate-800/40 border border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <Server className="w-4 h-4 text-cyan-400" />
              <div>
                <div className="text-[11px] text-slate-400 font-medium">Gateway URL</div>
                <div className="text-xs font-mono text-slate-200 truncate max-w-[150px] sm:max-w-[170px]">
                  {API_BASE_URL}
                </div>
              </div>
            </div>
            <a
              href={`${API_BASE_URL}/docs`}
              target="_blank"
              rel="noreferrer"
              className="text-slate-400 hover:text-cyan-300 p-1 rounded transition-colors"
              title="Open Swagger Docs"
            >
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          </div>

          {/* Database Status */}
          <div className="p-3.5 rounded-xl bg-slate-800/40 border border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <Database className="w-4 h-4 text-cyan-400" />
              <div>
                <div className="text-[11px] text-slate-400 font-medium">Neon PostgreSQL</div>
                <div className="text-xs font-medium">
                  {isConnected ? (
                    isDbConnected ? (
                      <span className="text-emerald-400">Connected (PostGIS)</span>
                    ) : (
                      <span className="text-amber-400" title={data?.database_detail || 'Unreachable'}>
                        Unreachable (safe)
                      </span>
                    )
                  ) : (
                    <span className="text-slate-500">—</span>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Error Detail or Offline Guidance */}
        {isError && (
          <div className="mt-4 p-3 rounded-lg bg-rose-950/20 border border-rose-900/40 text-xs text-rose-300 relative z-10">
            <p className="font-semibold mb-1">Cannot reach backend server:</p>
            <p className="text-rose-400 font-mono text-[11px] break-all">
              {error?.message || 'Connection refused. Ensure FastAPI is running on ' + API_BASE_URL}
            </p>
          </div>
        )}

        {/* Diagnostic note when DB unreachable but backend ok */}
        {isConnected && !isDbConnected && (
          <div className="mt-4 p-3 rounded-lg bg-amber-950/20 border border-amber-900/40 text-xs text-amber-300 relative z-10">
            <span className="font-semibold">Note:</span> Backend is online. Database is unreachable or pending configuration in <code className="px-1 py-0.5 bg-amber-950/50 rounded text-amber-200">.env</code>. The API remains fully resilient without crashing.
          </div>
        )}
      </div>
    </div>
  );
};
