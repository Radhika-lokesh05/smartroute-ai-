import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Navigation, LogOut, User as UserIcon, Volume2, VolumeX, ShieldAlert, Hospital as HospitalIcon, Siren } from 'lucide-react';
import { useAuth } from '@/auth/useAuth';
import { RealtimeConnectionStatus } from '@/types/incident';

interface HeaderProps {
  connectionStatus?: RealtimeConnectionStatus;
  incidentCount?: number;
  onToggleIncidents?: () => void;
  isSoundEnabled?: boolean;
  onToggleSound?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  connectionStatus = 'offline',
  incidentCount = 0,
  onToggleIncidents,
  isSoundEnabled = false,
  onToggleSound,
}) => {
  const { user, logout } = useAuth();
  const location = useLocation();

  if (!user) return null;

  const isActive = (path: string) => location.pathname === path;

  const renderStatusBadge = () => {
    const configs: Record<RealtimeConnectionStatus, { bg: string; dot: string; text: string; label: string }> = {
      live: { bg: 'bg-emerald-950/80 border-emerald-800/80', dot: 'bg-emerald-400 animate-pulse', text: 'text-emerald-400', label: 'Live' },
      reconnecting: { bg: 'bg-amber-950/80 border-amber-800/80', dot: 'bg-amber-400 animate-spin', text: 'text-amber-400', label: 'Reconnecting' },
      connecting: { bg: 'bg-cyan-950/80 border-cyan-800/80', dot: 'bg-cyan-400 animate-pulse', text: 'text-cyan-400', label: 'Connecting' },
      offline: { bg: 'bg-slate-800 border-slate-700', dot: 'bg-slate-500', text: 'text-slate-400', label: 'Offline' },
    };
    const c = configs[connectionStatus] || configs.offline;
    return (
      <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded-full border text-[10px] font-medium ${c.bg} ${c.text}`}>
        <span className={`w-1.5 h-1.5 rounded-full ${c.dot}`} />
        <span>{c.label}</span>
      </div>
    );
  };

  return (
    <header className="h-14 border-b border-slate-800/80 bg-slate-900/90 backdrop-blur-md sticky top-0 z-50 px-4 flex items-center justify-between">
      <div className="flex items-center gap-2.5">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-cyan-600 to-teal-400 flex items-center justify-center shadow-md shadow-cyan-500/20">
          <Navigation className="w-4 h-4 text-slate-950 rotate-45" />
        </div>
        <div className="flex items-center gap-2">
          <span className="font-display font-bold text-base tracking-tight bg-gradient-to-r from-cyan-400 to-teal-300 bg-clip-text text-transparent">
            SmartRoute AI
          </span>
          <span className="hidden sm:inline-block text-[9px] uppercase font-mono px-1.5 py-0.5 rounded bg-cyan-950 text-cyan-400 border border-cyan-800/40">
            Realtime Nav
          </span>
        </div>

        <nav className="flex items-center gap-1 ml-2 sm:ml-4" aria-label="Main Navigation">
          <Link
            to="/"
            className={`px-2 py-1 rounded-md text-xs font-medium transition-colors ${
              isActive('/')
                ? 'bg-cyan-950/70 text-cyan-300 border border-cyan-800/60'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Map
          </Link>
          <Link
            to="/hospitals"
            className={`flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium transition-colors ${
              isActive('/hospitals')
                ? 'bg-cyan-950/70 text-cyan-300 border border-cyan-800/60'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <HospitalIcon className="w-3 h-3 text-rose-400" />
            <span className="hidden xs:inline sm:inline">Hospitals</span>
          </Link>
          {user.role === 'ambulance' && (
            <Link
              to="/ambulance"
              className={`flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium transition-colors ${
                isActive('/ambulance')
                  ? 'bg-amber-950/70 text-amber-300 border border-amber-800/60'
                  : 'text-amber-400/80 hover:text-amber-300'
              }`}
            >
              <Siren className="w-3 h-3 text-amber-400 animate-pulse" />
              <span>Ambulance</span>
            </Link>
          )}
          {user.role === 'admin' && (
            <Link
              to="/admin"
              className={`flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium transition-colors ${
                isActive('/admin')
                  ? 'bg-purple-950/70 text-purple-300 border border-purple-800/60'
                  : 'text-purple-400/80 hover:text-purple-300'
              }`}
            >
              <span>Admin</span>
            </Link>
          )}
        </nav>
      </div>

      <div className="flex items-center gap-2 sm:gap-3">
        {/* Realtime WebSocket Indicator */}
        {renderStatusBadge()}

        {/* Sound alerts toggle */}
        {onToggleSound && (
          <button
            type="button"
            onClick={onToggleSound}
            title={isSoundEnabled ? 'Mute alert sounds' : 'Enable alert sounds'}
            className="p-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-300 transition-colors border border-slate-700/60"
          >
            {isSoundEnabled ? <Volume2 className="w-3.5 h-3.5 text-cyan-400" /> : <VolumeX className="w-3.5 h-3.5 text-slate-400" />}
          </button>
        )}

        {/* Nearby Incidents Panel toggle */}
        {onToggleIncidents && (
          <button
            type="button"
            onClick={onToggleIncidents}
            title="View nearby incidents"
            className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-200 transition-colors border border-slate-700/60 text-xs font-medium"
          >
            <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
            <span className="hidden sm:inline">Incidents</span>
            <span className="px-1.5 py-0.2 rounded-full text-[10px] font-mono bg-amber-500/20 text-amber-300 border border-amber-500/30">
              {incidentCount}
            </span>
          </button>
        )}

        <div className="hidden md:flex items-center gap-1.5 px-2 py-1 rounded-lg bg-slate-800/60 border border-slate-700/50 text-xs">
          <UserIcon className="w-3.5 h-3.5 text-cyan-400" />
          <span className="font-medium text-slate-200 max-w-[120px] truncate">{user.name}</span>
          <span className="text-[10px] font-mono px-1.5 py-0.2 rounded-full uppercase bg-slate-700/60 text-slate-300">{user.role}</span>
        </div>

        <button
          onClick={logout}
          title="Sign out"
          className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-rose-300 hover:text-rose-200 bg-rose-950/30 hover:bg-rose-900/40 border border-rose-800/40 rounded-lg transition-colors"
        >
          <LogOut className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">Logout</span>
        </button>
      </div>
    </header>
  );
};
