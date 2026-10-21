import React from 'react';
import { WeatherInfo } from '@/types/routing';

interface WeatherChipProps {
  weather?: WeatherInfo | null;
}

const WEATHER_ICONS: Record<string, string> = {
  Clear: '☀️',
  Overcast: '☁️',
  Fog: '🌫️',
  Rain: '🌧️',
  Windy: '💨',
};

export const WeatherChip: React.FC<WeatherChipProps> = ({ weather }) => {
  if (!weather) return null;

  const icon = WEATHER_ICONS[weather.condition] || '🌤️';
  const temp = Math.round(weather.temperature_c);
  const precip = (weather.precipitation_mm || 0).toFixed(1);
  const visKm = ((weather.visibility_m || 10000) / 1000).toFixed(1);

  const tooltipText = `Precipitation: ${precip} mm | Visibility: ${visKm} km`;

  return (
    <div
      data-testid="weather-chip"
      title={tooltipText}
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-800/80 border border-slate-700/80 text-slate-200 shadow-sm cursor-help hover:border-slate-600 transition-colors"
    >
      <span className="text-sm leading-none" role="img" aria-label={weather.condition}>
        {icon}
      </span>
      <span className="font-semibold">{weather.condition}</span>
      <span className="text-slate-400">, {temp}°C</span>
    </div>
  );
};
