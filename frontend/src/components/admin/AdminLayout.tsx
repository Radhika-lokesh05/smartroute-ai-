import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Menu, Sparkles } from 'lucide-react';
import { AdminSidebar } from './AdminSidebar';

interface AdminLayoutProps {
  isSimulatedActive?: boolean;
}

export const AdminLayout: React.FC<AdminLayoutProps> = ({ isSimulatedActive = false }) => {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col md:flex-row antialiased">
      <AdminSidebar mobileOpen={mobileOpen} onCloseMobile={() => setMobileOpen(false)} />

      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 border-b border-slate-800/80 bg-slate-900/60 backdrop-blur-md px-4 flex items-center justify-between sticky top-0 z-30">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMobileOpen(true)}
              className="md:hidden p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800"
            >
              <Menu className="w-5 h-5" />
            </button>
            <span className="text-xs font-mono uppercase tracking-wider text-slate-400">
              Operations Control
            </span>
          </div>

          <div className="flex items-center gap-3">
            {isSimulatedActive && (
              <div
                data-testid="simulated-badge"
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-purple-500/15 border border-purple-500/30 text-[11px] font-semibold text-purple-300 animate-pulse"
              >
                <Sparkles className="w-3 h-3 text-purple-400" />
                <span>Simulated data</span>
              </div>
            )}
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
              <span className="text-xs text-slate-300 font-mono">LIVE CLUSTER</span>
            </div>
          </div>
        </header>

        <main className="flex-1 p-4 md:p-6 overflow-x-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
