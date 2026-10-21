import React from 'react';
import { Link } from 'react-router-dom';
import { Compass, Home, MapPin } from 'lucide-react';

export const NotFoundPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-slate-900 border border-slate-800 rounded-2xl p-8 shadow-2xl text-center">
        <div className="w-16 h-16 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center mx-auto mb-6">
          <Compass className="w-8 h-8 text-cyan-400 animate-pulse" />
        </div>

        <span className="text-xs font-semibold uppercase tracking-wider text-cyan-400 bg-cyan-950/50 px-3 py-1 rounded-full border border-cyan-800/40">
          404 Not Found
        </span>

        <h1 className="text-2xl font-bold text-white mt-4 mb-2 font-display">
          Route Off the Map
        </h1>
        <p className="text-sm text-slate-400 mb-6">
          The coordinate or page you requested does not exist in our traffic routing network.
        </p>

        <div className="flex flex-col sm:flex-row gap-3">
          <Link
            to="/"
            className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-semibold text-sm transition-colors shadow-lg shadow-cyan-600/20"
          >
            <Home className="w-4 h-4" />
            Home
          </Link>
          <Link
            to="/map"
            className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold text-sm transition-colors border border-slate-700"
          >
            <MapPin className="w-4 h-4" />
            Live Map
          </Link>
        </div>
      </div>
    </div>
  );
};
