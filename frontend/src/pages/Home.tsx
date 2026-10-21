import React from 'react';
import { useHealth } from '@/hooks/useHealth';
import { StatusCard } from '@/components/StatusCard';
import { 
  ShieldAlert, 
  Navigation, 
  Siren, 
  Building2, 
  Cpu, 
  GitBranch 
} from 'lucide-react';

export const Home: React.FC = () => {
  const { data, isLoading, isError, error, refetch, isFetching } = useHealth();

  return (
    <div className="min-h-screen bg-brand-dark bg-grid-pattern relative flex flex-col justify-between">
      {/* Top Navigation Bar */}
      <header className="border-b border-slate-800/80 bg-slate-900/60 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-cyan-600 to-teal-400 flex items-center justify-center shadow-lg shadow-cyan-500/20">
              <Navigation className="w-5 h-5 text-slate-950 font-black rotate-45" />
            </div>
            <div>
              <span className="font-display font-bold text-lg tracking-tight bg-gradient-to-r from-cyan-400 via-teal-300 to-white bg-clip-text text-transparent">
                SmartRoute AI
              </span>
              <span className="ml-2 text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-cyan-950 text-cyan-400 border border-cyan-800/50">
                v0.1.0-alpha
              </span>
            </div>
          </div>

          <div className="flex items-center gap-4 text-xs font-mono text-slate-400">
            <div className="hidden sm:flex items-center gap-2 px-2.5 py-1 rounded-full bg-slate-800/60 border border-slate-700/50">
              <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
              <span>Monorepo Initialized</span>
            </div>
            <a
              href="https://github.com"
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1.5 text-slate-400 hover:text-cyan-300 transition-colors"
            >
              <GitBranch className="w-3.5 h-3.5" />
              <span className="hidden md:inline">smartroute-ai</span>
            </a>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-5xl mx-auto px-4 sm:px-6 py-10 sm:py-16 w-full flex flex-col items-center justify-center">
        {/* Hero Section */}
        <div className="text-center max-w-2xl mx-auto mb-10">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-950/50 border border-cyan-500/30 text-cyan-300 text-xs font-medium mb-4 shadow-sm">
            <Siren className="w-3.5 h-3.5 text-rose-400 animate-pulse" />
            <span>Emergency-Aware Dynamic Routing Core</span>
          </div>

          <h1 className="text-3xl sm:text-5xl font-display font-extrabold tracking-tight text-white mb-4">
            Next-Gen Emergency <br />
            <span className="bg-gradient-to-r from-cyan-400 via-teal-300 to-emerald-400 bg-clip-text text-transparent">
              Traffic Intelligence
            </span>
          </h1>

          <p className="text-slate-400 text-sm sm:text-base leading-relaxed">
            Real-time ambulance priority routing, live accident hazard rerouting, 
            and automated hospital emergency department triage suggestions.
          </p>
        </div>

        {/* Live System Telemetry / Health Card */}
        <StatusCard
          isLoading={isLoading}
          isError={isError}
          data={data}
          error={error}
          onRefresh={() => refetch()}
          isFetching={isFetching}
        />

        {/* Modular Architecture Pillars */}
        <div className="mt-12 w-full grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 max-w-4xl">
          <div className="p-4 rounded-xl bg-slate-900/50 border border-slate-800/80 hover:border-cyan-500/30 transition-all group">
            <div className="w-8 h-8 rounded-lg bg-rose-500/10 text-rose-400 flex items-center justify-center mb-3 group-hover:scale-110 transition-transform">
              <Siren className="w-4 h-4" />
            </div>
            <h2 className="text-xs font-bold text-slate-200 uppercase tracking-wider mb-1">
              Ambulance Priority
            </h2>
            <p className="text-[11px] text-slate-400 leading-normal">
              Corridor green-wave scheduling and priority traffic rerouting.
            </p>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/50 border border-slate-800/80 hover:border-cyan-500/30 transition-all group">
            <div className="w-8 h-8 rounded-lg bg-amber-500/10 text-amber-400 flex items-center justify-center mb-3 group-hover:scale-110 transition-transform">
              <ShieldAlert className="w-4 h-4" />
            </div>
            <h2 className="text-xs font-bold text-slate-200 uppercase tracking-wider mb-1">
              Incident Alerts
            </h2>
            <p className="text-[11px] text-slate-400 leading-normal">
              PostGIS-backed spatial collision detection and congestion diversion.
            </p>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/50 border border-slate-800/80 hover:border-cyan-500/30 transition-all group">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center mb-3 group-hover:scale-110 transition-transform">
              <Building2 className="w-4 h-4" />
            </div>
            <h2 className="text-xs font-bold text-slate-200 uppercase tracking-wider mb-1">
              Hospital Triage
            </h2>
            <p className="text-[11px] text-slate-400 leading-normal">
              Bed capacity and trauma center proximity telemetry.
            </p>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/50 border border-slate-800/80 hover:border-cyan-500/30 transition-all group">
            <div className="w-8 h-8 rounded-lg bg-cyan-500/10 text-cyan-400 flex items-center justify-center mb-3 group-hover:scale-110 transition-transform">
              <Cpu className="w-4 h-4" />
            </div>
            <h2 className="text-xs font-bold text-slate-200 uppercase tracking-wider mb-1">
              ML Traffic Models
            </h2>
            <p className="text-[11px] text-slate-400 leading-normal">
              LightGBM velocity forecasts combined with Open-Meteo weather factors.
            </p>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 bg-slate-950/60 py-6 text-center text-xs text-slate-500">
        <p>SmartRoute AI — Built with FastAPI, PostgreSQL + PostGIS, Vite, React & Tailwind CSS.</p>
      </footer>
    </div>
  );
};
