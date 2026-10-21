import L from 'leaflet';
import { IncidentStatus, IncidentType } from '@/types/incident';

interface IconConfig {
  bgColor: string;
  borderColor: string;
  ringColor: string;
  svgIcon: string;
}

const TYPE_CONFIGS: Record<IncidentType, IconConfig> = {
  accident: {
    bgColor: '#e11d48', // Rose-600
    borderColor: '#fda4af', // Rose-300
    ringColor: 'rgba(225, 29, 72, 0.4)',
    // Car crash / collision icon
    svgIcon: `
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
      </svg>
    `,
  },
  blockage: {
    bgColor: '#ea580c', // Orange-600
    borderColor: '#fed7aa', // Orange-200
    ringColor: 'rgba(234, 88, 12, 0.4)',
    // Barrier / minus-circle icon
    svgIcon: `
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"/>
        <line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/>
      </svg>
    `,
  },
  hazard: {
    bgColor: '#ca8a04', // Yellow-600
    borderColor: '#fef08a', // Yellow-200
    ringColor: 'rgba(202, 138, 4, 0.4)',
    // Hazard triangle icon
    svgIcon: `
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
        <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>
        <line x1="12" y1="9" x2="12" y2="13"/>
        <line x1="12" y1="17" x2="12.01" y2="17"/>
      </svg>
    `,
  },
};

export function createIncidentDivIcon(type: IncidentType, status: IncidentStatus): L.DivIcon {
  const config = TYPE_CONFIGS[type] || TYPE_CONFIGS.hazard;
  const isValidated = status === 'validated';

  const pulseRingHtml = isValidated
    ? `<div class="absolute -inset-1.5 rounded-full animate-ping opacity-60" style="background-color: ${config.ringColor};"></div>`
    : '';

  const borderStyle = isValidated
    ? `border: 2px solid ${config.borderColor}; box-shadow: 0 0 14px ${config.bgColor};`
    : `border: 2px dashed ${config.borderColor}; opacity: 0.9;`;

  const html = `
    <div class="relative flex items-center justify-center w-8 h-8 select-none">
      ${pulseRingHtml}
      <div
        class="relative w-8 h-8 rounded-full flex items-center justify-center text-white shadow-xl transition-transform hover:scale-110"
        style="background-color: ${config.bgColor}; ${borderStyle}"
      >
        ${config.svgIcon}
      </div>
    </div>
  `;

  return L.divIcon({
    html,
    className: 'incident-marker-icon',
    iconSize: [32, 32],
    iconAnchor: [16, 16],
    popupAnchor: [0, -18],
  });
}
