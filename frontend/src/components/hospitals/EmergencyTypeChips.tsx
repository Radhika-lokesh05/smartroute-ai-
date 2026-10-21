import React from 'react';
import { EmergencyType } from '@/types/hospital';

export const EMERGENCY_SPECIALTIES: { id: EmergencyType; label: string }[] = [
  { id: 'general', label: 'General' },
  { id: 'trauma', label: 'Trauma' },
  { id: 'cardiac', label: 'Cardiac' },
  { id: 'burns', label: 'Burns' },
  { id: 'maternity', label: 'Maternity' },
  { id: 'pediatric', label: 'Pediatric' },
];

interface EmergencyTypeChipsProps {
  selectedType: EmergencyType;
  onSelect: (type: EmergencyType) => void;
}

export const EmergencyTypeChips: React.FC<EmergencyTypeChipsProps> = ({
  selectedType,
  onSelect,
}) => {
  return (
    <div className="flex items-center gap-1.5 overflow-x-auto pb-2 scrollbar-none" role="radiogroup" aria-label="Emergency specialty filter">
      {EMERGENCY_SPECIALTIES.map((spec) => {
        const isSelected = selectedType === spec.id;
        return (
          <button
            key={spec.id}
            type="button"
            role="radio"
            aria-checked={isSelected}
            onClick={() => onSelect(spec.id)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-all border ${
              isSelected
                ? 'bg-rose-950/80 text-rose-300 border-rose-600 shadow-sm shadow-rose-900/30 font-semibold'
                : 'bg-slate-900/80 text-slate-400 border-slate-800 hover:border-slate-700 hover:text-slate-300'
            }`}
          >
            {spec.label}
          </button>
        );
      })}
    </div>
  );
};
