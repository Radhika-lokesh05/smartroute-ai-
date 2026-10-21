import React, { useState, useEffect, useRef } from 'react';
import { fetchAutocomplete } from '@/api/geocode';
import { GeocodeResult } from '@/types/geocode';
import { Search, Loader2, MapPin, X } from 'lucide-react';

interface PlaceSearchInputProps {
  id: string;
  label: string;
  placeholder?: string;
  value: string;
  onChange: (text: string) => void;
  onSelect: (result: GeocodeResult) => void;
  focusLat?: number;
  focusLng?: number;
}

export const PlaceSearchInput: React.FC<PlaceSearchInputProps> = ({
  id, label, placeholder = 'Search place in India...', value, onChange, onSelect, focusLat, focusLng,
}) => {
  const [results, setResults] = useState<GeocodeResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const containerRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (abortControllerRef.current) abortControllerRef.current.abort();
    if (value.trim().length < 3) {
      setResults([]);
      setIsLoading(false);
      setIsOpen(false);
      return;
    }

    setIsLoading(true);
    const controller = new AbortController();
    abortControllerRef.current = controller;

    const timer = setTimeout(async () => {
      try {
        const data = await fetchAutocomplete(value, focusLat, focusLng, controller.signal);
        setResults(data.results || []);
        setIsOpen(true);
        setHighlightedIndex(-1);
      } catch (err: any) {
        if (err.name !== 'CanceledError' && err.name !== 'AbortError') setResults([]);
      } finally {
        setIsLoading(false);
      }
    }, 350);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [value, focusLat, focusLng]);

  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setIsOpen(false);
    };
    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!isOpen || results.length === 0) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightedIndex((prev) => (prev < results.length - 1 ? prev + 1 : 0));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightedIndex((prev) => (prev > 0 ? prev - 1 : results.length - 1));
    } else if (e.key === 'Enter' && highlightedIndex >= 0) {
      e.preventDefault();
      onSelect(results[highlightedIndex]);
      setIsOpen(false);
    } else if (e.key === 'Escape') {
      setIsOpen(false);
    }
  };

  return (
    <div ref={containerRef} className="relative w-full">
      <label htmlFor={id} className="block text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-1">
        {label}
      </label>
      <div className="relative flex items-center">
        <Search className="w-4 h-4 text-slate-500 absolute left-3 pointer-events-none" />
        <input
          id={id}
          type="text"
          role="combobox"
          aria-expanded={isOpen}
          aria-autocomplete="list"
          aria-controls={`${id}-listbox`}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onFocus={() => results.length > 0 && setIsOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className="w-full pl-9 pr-8 py-2 rounded-xl bg-slate-900 border border-slate-700/80 text-xs sm:text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500 transition-all"
        />
        {isLoading && <Loader2 className="w-3.5 h-3.5 text-cyan-400 animate-spin absolute right-3" />}
        {!isLoading && value && (
          <button type="button" onClick={() => onChange('')} className="absolute right-2.5 text-slate-400 hover:text-slate-200">
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {isOpen && (
        <ul
          id={`${id}-listbox`}
          role="listbox"
          className="absolute z-50 left-0 right-0 mt-1 max-h-56 overflow-y-auto rounded-xl bg-slate-900 border border-slate-700 shadow-2xl divide-y divide-slate-800 text-xs"
        >
          {results.length === 0 && !isLoading && (
            <li className="p-3 text-center text-slate-500">No matching locations found</li>
          )}
          {results.map((item, idx) => (
            <li
              key={`${item.lat}-${item.lng}-${idx}`}
              role="option"
              aria-selected={idx === highlightedIndex}
              onClick={() => { onSelect(item); setIsOpen(false); }}
              className={`p-2.5 flex items-start gap-2.5 cursor-pointer transition-colors ${
                idx === highlightedIndex ? 'bg-cyan-950/60 text-cyan-200' : 'hover:bg-slate-800/80 text-slate-300'
              }`}
            >
              <MapPin className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
              <div className="flex-1 truncate">
                <p className="font-medium text-slate-100 truncate">{item.label}</p>
                {item.locality && <p className="text-[10px] text-slate-400">{item.locality}</p>}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
