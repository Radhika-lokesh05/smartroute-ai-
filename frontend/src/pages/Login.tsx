import React, { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '@/auth/useAuth';
import { Navigation, LogIn, AlertCircle, Loader2, Clock } from 'lucide-react';
import { formatAuthError } from '@/utils/authError';

export const Login: React.FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const isExpired = searchParams.get('expired') === '1';

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!email || !password) {
      setError('Please provide both email and password.');
      return;
    }

    try {
      setIsSubmitting(true);
      await login({ email: email.trim(), password });
      navigate('/', { replace: true });
    } catch (err: any) {
      setError(formatAuthError(err, 'Authentication failed. Please check credentials.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-brand-dark bg-grid-pattern flex flex-col justify-center items-center px-4 py-12">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex w-12 h-12 rounded-2xl bg-gradient-to-tr from-cyan-600 to-teal-400 items-center justify-center shadow-lg shadow-cyan-500/20 mb-3">
            <Navigation className="w-6 h-6 text-slate-950 rotate-45" />
          </div>
          <h1 className="font-display font-extrabold text-2xl text-white tracking-tight">
            Sign In to SmartRoute AI
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Emergency-aware traffic intelligence and routing portal
          </p>
        </div>

        <div className="glass-panel rounded-2xl p-6 sm:p-8 shadow-2xl border border-slate-800">
          {isExpired && !error && (
            <div className="mb-5 p-3 rounded-xl bg-amber-950/40 border border-amber-800/50 flex items-start gap-2.5 text-amber-300 text-xs">
              <Clock className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
              <span>Your session has expired. Please sign in again to continue.</span>
            </div>
          )}

          {error && (
            <div className="mb-5 p-3 rounded-xl bg-rose-950/40 border border-rose-800/50 flex items-start gap-2.5 text-rose-300 text-xs">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">
                Email Address
              </label>
              <input
                id="login-email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@domain.com"
                className="w-full px-3.5 py-2.5 rounded-xl bg-slate-900/90 border border-slate-700/80 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">
                Password
              </label>
              <input
                id="login-password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full px-3.5 py-2.5 rounded-xl bg-slate-900/90 border border-slate-700/80 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500"
              />
            </div>

            <button
              id="login-submit-btn"
              type="submit"
              disabled={isSubmitting}
              className="w-full mt-2 py-2.5 px-4 rounded-xl bg-gradient-to-r from-cyan-600 to-teal-500 hover:from-cyan-500 hover:to-teal-400 text-slate-950 font-semibold text-sm shadow-lg shadow-cyan-600/20 transition-all flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Signing In...</span>
                </>
              ) : (
                <>
                  <LogIn className="w-4 h-4" />
                  <span>Sign In</span>
                </>
              )}
            </button>
          </form>

          <div className="mt-6 text-center text-xs text-slate-400">
            Don't have an account?{' '}
            <Link to="/register" className="text-cyan-400 hover:text-cyan-300 font-medium transition-colors">
              Register here
            </Link>
          </div>

          <div className="mt-5 p-3 rounded-xl bg-slate-900/60 border border-slate-800 text-[11px] text-slate-400">
            <div className="flex items-center justify-between mb-1">
              <span className="font-semibold text-slate-300">Default Admin Account</span>
              <button
                type="button"
                onClick={() => {
                  setEmail('admin@smartroute.ai');
                  setPassword('adminpassword123');
                }}
                className="text-cyan-400 hover:text-cyan-300 font-medium underline text-[11px]"
              >
                Auto-fill
              </button>
            </div>
            <code className="text-slate-400 font-mono text-[10px] block">admin@smartroute.ai / adminpassword123</code>
          </div>
        </div>
      </div>
    </div>
  );
};
