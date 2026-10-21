import React, { useState, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Incident, IncidentType } from '@/types/incident';
import { reportIncident, mapIncidentError } from '@/api/incidents';
import { AlertCircle, CheckCircle2, ShieldAlert, X, Car, Construction, AlertTriangle } from 'lucide-react';

interface ReportIncidentModalProps {
  isOpen: boolean;
  onClose: () => void;
  userLocation: { lat: number; lng: number } | null;
  onSuccessToast?: (msg: string) => void;
}

export const ReportIncidentModal: React.FC<ReportIncidentModalProps> = ({
  isOpen,
  onClose,
  userLocation,
  onSuccessToast,
}) => {
  const queryClient = useQueryClient();
  const [incidentType, setIncidentType] = useState<IncidentType>('accident');
  const [note, setNote] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setNote('');
      setErrorMessage(null);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!userLocation) {
      setErrorMessage('GPS fix required to report road incidents.');
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const { incident, wasMerged } = await reportIncident({
        lat: userLocation.lat,
        lng: userLocation.lng,
        type: incidentType,
        note: note.trim() || undefined,
      });

      // Update query cache
      queryClient.setQueriesData<Incident[]>({ queryKey: ['incidents', 'nearby'] }, (old = []) => {
        const idx = old.findIndex((i) => i.id === incident.id);
        if (idx >= 0) {
          const next = [...old];
          next[idx] = incident;
          return next;
        }
        return [incident, ...old];
      });

      const message = wasMerged
        ? 'We added your confirmation to the existing report nearby!'
        : 'Incident reported successfully. Thank you for alerting drivers!';

      onSuccessToast?.(message);
      onClose();
    } catch (err) {
      setErrorMessage(mapIncidentError(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const types: Array<{ type: IncidentType; label: string; icon: React.FC<{ className?: string }>; color: string }> = [
    { type: 'accident', label: 'Accident', icon: Car, color: 'text-rose-400 bg-rose-950/60 border-rose-800/80' },
    { type: 'blockage', label: 'Blockage', icon: Construction, color: 'text-amber-400 bg-amber-950/60 border-amber-800/80' },
    { type: 'hazard', label: 'Hazard', icon: AlertTriangle, color: 'text-yellow-400 bg-yellow-950/60 border-yellow-800/80' },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 bg-slate-950/80 backdrop-blur-sm animate-fade-in">
      <div className="w-full sm:max-w-md bg-slate-900 border border-slate-800 rounded-t-2xl sm:rounded-2xl shadow-2xl p-5 text-slate-100 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-5 h-5 text-cyan-400" />
            <h3 className="font-semibold text-base text-slate-100">Report Road Incident</h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {errorMessage && (
          <div className="p-2.5 rounded-lg bg-rose-950/80 border border-rose-800/80 text-rose-200 text-xs flex items-start gap-2">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
            <span>{errorMessage}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-2">Select Incident Type</label>
            <div className="grid grid-cols-3 gap-2">
              {types.map((t) => {
                const Icon = t.icon;
                const isSelected = incidentType === t.type;
                return (
                  <button
                    key={t.type}
                    type="button"
                    onClick={() => setIncidentType(t.type)}
                    className={`p-3 rounded-xl border flex flex-col items-center gap-1.5 transition-all ${
                      isSelected
                        ? `${t.color} ring-2 ring-cyan-400/80 shadow-lg`
                        : 'border-slate-800 bg-slate-950/50 hover:bg-slate-800/60 text-slate-400'
                    }`}
                  >
                    <Icon className="w-5 h-5" />
                    <span className="text-xs font-semibold">{t.label}</span>
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between text-xs font-medium text-slate-300 mb-1.5">
              <label htmlFor="note">Optional Note</label>
              <span className={`text-[11px] ${note.length >= 190 ? 'text-amber-400' : 'text-slate-500'}`}>
                {note.length} / 200
              </span>
            </div>
            <textarea
              id="note"
              value={note}
              onChange={(e) => setNote(e.target.value.slice(0, 200))}
              placeholder="e.g. Fallen tree blocking left lane after flyover..."
              rows={3}
              className="w-full px-3 py-2 text-xs bg-slate-950/80 border border-slate-700/80 rounded-xl text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors resize-none"
            />
          </div>

          <div className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-800 text-[11px] text-slate-400 flex items-start gap-2">
            <CheckCircle2 className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
            <span>
              Reporting at your current GPS location ({userLocation ? `${userLocation.lat.toFixed(4)}, ${userLocation.lng.toFixed(4)}` : 'Detecting...'})
            </span>
          </div>

          <button
            type="submit"
            disabled={isSubmitting || !userLocation}
            className="w-full py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-teal-500 hover:from-cyan-400 hover:to-teal-400 text-slate-950 font-semibold text-sm transition-all shadow-lg shadow-cyan-500/20 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSubmitting ? 'Submitting Report...' : !userLocation ? 'GPS Fix Required' : 'Submit Incident Report'}
          </button>
        </form>
      </div>
    </div>
  );
};
