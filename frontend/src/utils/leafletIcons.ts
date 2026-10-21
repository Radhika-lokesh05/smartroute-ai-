import L from 'leaflet';

/**
 * Fix for Leaflet default icon asset URLs in Vite bundlers.
 */
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

/**
 * Custom SVG DivIcon for the route Origin (Emerald A).
 */
export const originIcon = L.divIcon({
  className: 'custom-origin-icon',
  html: `
    <div style="position: relative; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;">
      <div style="background: #10B981; width: 28px; height: 28px; border-radius: 50% 50% 50% 0; transform: rotate(-45deg); box-shadow: 0 4px 12px rgba(16, 185, 129, 0.5); border: 2px solid #ffffff; display: flex; align-items: center; justify-content: center;">
        <span style="transform: rotate(45deg); color: #064e3b; font-weight: 800; font-size: 11px;">A</span>
      </div>
    </div>
  `,
  iconSize: [32, 32],
  iconAnchor: [16, 30],
  popupAnchor: [0, -28],
});

/**
 * Custom SVG DivIcon for the route Destination (Crimson B).
 */
export const destinationIcon = L.divIcon({
  className: 'custom-destination-icon',
  html: `
    <div style="position: relative; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;">
      <div style="background: #EF4444; width: 28px; height: 28px; border-radius: 50% 50% 50% 0; transform: rotate(-45deg); box-shadow: 0 4px 12px rgba(239, 68, 68, 0.5); border: 2px solid #ffffff; display: flex; align-items: center; justify-content: center;">
        <span style="transform: rotate(45deg); color: #450a0a; font-weight: 800; font-size: 11px;">B</span>
      </div>
    </div>
  `,
  iconSize: [32, 32],
  iconAnchor: [16, 30],
  popupAnchor: [0, -28],
});

/**
 * Custom pulsating live user location marker (Blue beacon).
 */
export const userLocationIcon = L.divIcon({
  className: 'custom-user-location-icon',
  html: `
    <div style="position: relative; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center;">
      <div style="position: absolute; width: 24px; height: 24px; background: rgba(6, 182, 212, 0.4); border-radius: 50%; animation: ping 2s cubic-bezier(0, 0, 0.2, 1) infinite;"></div>
      <div style="position: relative; width: 14px; height: 14px; background: #06B6D4; border-radius: 50%; border: 2.5px solid #ffffff; box-shadow: 0 0 10px rgba(6, 182, 212, 0.8);"></div>
    </div>
  `,
  iconSize: [24, 24],
  iconAnchor: [12, 12],
});
