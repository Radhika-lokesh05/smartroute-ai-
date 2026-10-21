import React, { useState } from 'react';
import { Calendar, Clock } from 'lucide-react';

interface LeaveAtPickerProps {
  value?: string;
  onChange: (isoString?: string) => void;
}

function toLocalDatetimeString(date: Date): string {
  const pad = (n: number) => n.toString().padStart(2, '0');
  const y = date.getFullYear();
  const m = pad(date.getMonth() + 1);
  const d = pad(date.getDate());
  const hh = pad(date.getHours());
  const mm = pad(date.getMinutes());
  return `${y}-${m}-${d}T${hh}:${mm}`;
}

export const LeaveAtPicker: React.FC<LeaveAtPickerProps> = ({ value, onChange }) => {
  const [mode, setMode] = useState<'now' | 'custom'>(value ? 'custom' : 'now');

  const now = new Date();
  const minStr = toLocalDatetimeString(now);
  const maxDate = new Date(now.getTime() + 24 * 60 * 60 * 1000);
  const maxStr = toLocalDatetimeString(maxDate);

  const initialCustom = value ? toLocalDatetimeString(new Date(value)) : minStr;
  const [inputValue, setInputValue] = useState<string>(initialCustom);

  const handleModeChange = (newMode: 'now' | 'custom') => {
    setMode(newMode);
    if (newMode === 'now') {
      onChange(undefined);
    } else {
      const dateObj = new Date(inputValue || minStr);
      onChange(dateObj.toISOString());
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setInputValue(val);
    if (val) {
      const dateObj = new Date(val);
      onChange(dateObj.toISOString());
    }
  };

  return (
    <div className="space-y-2 p-2.5 rounded-xl bg-slate-900/60 border border-slate-800 text-xs">
      {/* Segmented Toggle */}
      <div className="flex items-center gap-1.5 p-1 rounded-lg bg-slate-950/80 border border-slate-800">
        <button
          type="button"
          onClick={() => handleModeChange('now')}
          className={`flex-1 flex items-center justify-center gap-1.5 py-1 px-2.5 rounded-md text-[11px] font-semibold transition-all ${
            mode === 'now'
              ? 'bg-cyan-500 text-slate-950 shadow-sm'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Clock className="w-3.5 h-3.5" />
          Leave now
        </button>
        <button
          type="button"
          onClick={() => handleModeChange('custom')}
          className={`flex-1 flex items-center justify-center gap-1.5 py-1 px-2.5 rounded-md text-[11px] font-semibold transition-all ${
            mode === 'custom'
              ? 'bg-cyan-500 text-slate-950 shadow-sm'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Calendar className="w-3.5 h-3.5" />
          Leave at...
        </button>
      </div>

      {/* Date-time input */}
      {mode === 'custom' && (
        <div className="pt-0.5">
          <input
            id="leave-at-input"
            aria-label="Departure time input"
            type="datetime-local"
            min={minStr}
            max={maxStr}
            value={inputValue}
            onChange={handleInputChange}
            className="w-full px-2.5 py-1.5 rounded-lg bg-slate-950 border border-slate-700 text-slate-100 text-xs focus:outline-none focus:border-cyan-500 transition-colors"
          />
        </div>
      )}

      {/* Notice */}
      <p data-testid="time-notice" className="text-[10px] text-slate-400 leading-snug">
        Time of day is not modelled with this dataset. Predictions reflect the selected date's day of week, month and forecast weather.
      </p>
    </div>
  );
};
