import React, { useState, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Incident } from '@/types/incident';
import { useAuth } from '@/auth/useAuth';
import { voteIncident, resolveIncident, mapIncidentError } from '@/api/incidents';
import { formatCountdownSeconds, formatDistance } from '@/utils/formatters';
import { ThumbsUp, ThumbsDown, CheckCircle, Clock, AlertTriangle } from 'lucide-react';

interface IncidentPopupProps {
  incident: Incident;
  userLocation: { lat: number; lng: number } | null;
}

export const IncidentPopup: React.FC<IncidentPopupProps> = ({ incident, userLocation }) => {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const [remaining, setRemaining] = useState<number>(incident.seconds_remaining);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Independent 1-second countdown timer that does NOT trigger map re-renders
  useEffect(() => {
    setRemaining(incident.seconds_remaining);
    const interval = setInterval(() => {
      setRemaining((prev) => Math.max(0, prev - 1));
    }, 1000);
    return () => clearInterval(interval);
  }, [incident.seconds_remaining, incident.id]);

  const canResolve = Boolean(
    user && (user.role === 'admin' || user.role === 'ambulance' || incident.user_voted)
  );

  const handleVote = async (voteType: 'confirm' | 'reject') => {
    if (!userLocation) {
      setErrorMessage('GPS location is required to vote.');
      return;
    }
    setIsSubmitting(true);
    setErrorMessage(null);
    try {
      const updated = await voteIncident(incident.id, {
        vote: voteType,
        voter_lat: userLocation.lat,
        voter_lng: userLocation.lng,
      });
      queryClient.setQueriesData<Incident[]>({ queryKey: ['incidents', 'nearby'] }, (old = []) =>
        old.map((i) => (i.id === updated.id ? { ...i, ...updated, user_voted: true, user_vote: voteType } : i))
      );
    } catch (err) {
      setErrorMessage(mapIncidentError(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResolve = async () => {
    setIsSubmitting(true);
    setErrorMessage(null);
    try {
      const resolved = await resolveIncident(incident.id);
      queryClient.setQueriesData<Incident[]>({ queryKey: ['incidents', 'nearby'] }, (old = []) =>
        old.filter((i) => i.id !== resolved.id)
      );
    } catch (err) {
      setErrorMessage(mapIncidentError(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-w-[220px] max-w-[280px] p-1 text-slate-100 font-sans text-xs">
      <div className="flex items-center justify-between gap-2 border-b border-slate-700/60 pb-2 mb-2">
        <span className="font-semibold uppercase tracking-wider text-[11px] text-cyan-400">
          {incident.incident_type}
        </span>
        <span
          className={`px-1.5 py-0.5 rounded text-[10px] font-medium uppercase ${
            incident.status === 'validated'
              ? 'bg-emerald-950 text-emerald-300 border border-emerald-800/60'
              : 'bg-amber-950 text-amber-300 border border-amber-800/60'
          }`}
        >
          {incident.status}
        </span>
      </div>

      {incident.note && (
        <p className="text-slate-300 text-[11px] mb-2 leading-relaxed italic bg-slate-800/50 p-1.5 rounded">
          "{incident.note}"
        </p>
      )}

      <div className="grid grid-cols-2 gap-1.5 text-[11px] text-slate-400 mb-2.5">
        <div className="flex items-center gap-1">
          <Clock className="w-3.5 h-3.5 text-cyan-400" />
          <span>{formatCountdownSeconds(remaining)}</span>
        </div>
        {incident.distance_m != null && (
          <div className="text-right">{formatDistance(incident.distance_m)} away</div>
        )}
        <div className="flex items-center gap-1">
          <ThumbsUp className="w-3.5 h-3.5 text-emerald-400" />
          <span>{incident.confirmations} confirms</span>
        </div>
        <div className="flex items-center gap-1 justify-end">
          <ThumbsDown className="w-3.5 h-3.5 text-rose-400" />
          <span>{incident.rejections} rejects</span>
        </div>
      </div>

      {errorMessage && (
        <div className="mb-2 p-1.5 rounded bg-rose-950/80 border border-rose-800/60 text-rose-300 text-[10px] flex items-start gap-1">
          <AlertTriangle className="w-3 h-3 shrink-0 mt-0.5 text-rose-400" />
          <span>{errorMessage}</span>
        </div>
      )}

      {incident.user_voted ? (
        <div className="py-1 px-2 rounded bg-slate-800/80 text-center text-slate-300 text-[10px] mb-2">
          You already voted ({incident.user_vote || 'confirmed'})
        </div>
      ) : !userLocation ? (
        <div className="py-1 px-2 rounded bg-slate-800/80 text-center text-slate-400 text-[10px] mb-2">
          GPS required to verify
        </div>
      ) : (
        <div className="flex items-center gap-1.5 mb-2">
          <button
            type="button"
            disabled={isSubmitting}
            onClick={() => handleVote('confirm')}
            className="flex-1 py-1 px-2 rounded bg-emerald-600/30 hover:bg-emerald-600/50 text-emerald-300 border border-emerald-600/50 font-medium text-[11px] flex items-center justify-center gap-1 transition-colors disabled:opacity-50"
          >
            <ThumbsUp className="w-3 h-3" />
            <span>Confirm</span>
          </button>
          <button
            type="button"
            disabled={isSubmitting}
            onClick={() => handleVote('reject')}
            className="flex-1 py-1 px-2 rounded bg-rose-600/30 hover:bg-rose-600/50 text-rose-300 border border-rose-600/50 font-medium text-[11px] flex items-center justify-center gap-1 transition-colors disabled:opacity-50"
          >
            <ThumbsDown className="w-3 h-3" />
            <span>Reject</span>
          </button>
        </div>
      )}

      {canResolve && (
        <button
          type="button"
          disabled={isSubmitting}
          onClick={handleResolve}
          className="w-full py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-600/50 text-[10px] font-medium flex items-center justify-center gap-1 transition-colors disabled:opacity-50"
        >
          <CheckCircle className="w-3 h-3 text-cyan-400" />
          <span>Mark as Resolved</span>
        </button>
      )}
    </div>
  );
};
