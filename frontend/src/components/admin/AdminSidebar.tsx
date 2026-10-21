import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  BarChart3,
  MapPin,
  Send,
  Truck,
  Users,
  ShieldCheck,
  Cpu,
  LogOut,
  X,
} from 'lucide-react';
import { useAuth } from '@/auth/useAuth';

interface AdminSidebarProps {
  mobileOpen: boolean;
  onCloseMobile: () => void;
}

const navItems = [
  { label: 'Overview', to: '/admin', icon: BarChart3, end: true },
  { label: 'Live Map', to: '/admin/map', icon: MapPin },
  { label: 'Dispatches', to: '/admin/dispatches', icon: Send },
  { label: 'Ambulances', to: '/admin/ambulances', icon: Truck },
  { label: 'Users', to: '/admin/users', icon: Users },
  { label: 'Audit Log', to: '/admin/audit', icon: ShieldCheck },
  { label: 'Model Info', to: '/admin/model', icon: Cpu },
];

export const AdminSidebar: React.FC<AdminSidebarProps> = ({ mobileOpen, onCloseMobile }) => {
  const { user, logout } = useAuth();

  const navContent = (
    <div className="flex flex-col h-full bg-slate-900 border-r border-slate-800 p-4">
      <div className="flex items-center justify-between pb-6 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-cyan-500/20 text-cyan-400 flex items-center justify-center font-bold text-sm">
            SR
          </div>
          <div>
            <h2 className="text-sm font-bold text-white tracking-wide">ADMIN CONSOLE</h2>
            <p className="text-[10px] text-slate-400">SmartRoute AI Control</p>
          </div>
        </div>
        <button
          onClick={onCloseMobile}
          className="md:hidden p-1 text-slate-400 hover:text-white"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      <nav className="flex-1 py-4 space-y-1 overflow-y-auto">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              onClick={onCloseMobile}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-medium transition ${
                  isActive
                    ? 'bg-cyan-500/15 text-cyan-400 border border-cyan-500/30'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                }`
              }
            >
              <Icon className="w-4 h-4 shrink-0" />
              <span>{item.label}</span>
            </NavLink>
          );
        })}
      </nav>

      <div className="pt-4 border-t border-slate-800 space-y-2">
        <div className="px-3 py-2 bg-slate-800/50 rounded-lg">
          <p className="text-xs font-medium text-slate-200 truncate">{user?.name}</p>
          <p className="text-[10px] font-mono text-cyan-400 truncate">{user?.email}</p>
        </div>
        <button
          onClick={() => logout()}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs text-red-400 hover:bg-red-500/10 transition"
        >
          <LogOut className="w-4 h-4 shrink-0" />
          <span>Sign Out</span>
        </button>
      </div>
    </div>
  );

  return (
    <>
      <aside className="hidden md:block w-60 shrink-0 h-screen sticky top-0">
        {navContent}
      </aside>
      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden flex">
          <div className="fixed inset-0 bg-black/60" onClick={onCloseMobile} />
          <div className="relative w-64 max-w-[80%] h-full z-10 shadow-2xl">
            {navContent}
          </div>
        </div>
      )}
    </>
  );
};
