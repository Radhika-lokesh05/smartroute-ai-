/**
 * Map Tile Provider Configuration
 * Configurable via Vite environment variables (VITE_TILE_URL, VITE_TILE_ATTRIBUTION)
 * allowing tile provider switches (e.g. Mapbox, Stadia, self-hosted tile server) without code changes.
 */

export const DEFAULT_TILE_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
export const DEFAULT_TILE_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

export const TILE_URL: string =
  (import.meta.env.VITE_TILE_URL as string) || DEFAULT_TILE_URL;

export const TILE_ATTRIBUTION: string =
  (import.meta.env.VITE_TILE_ATTRIBUTION as string) || DEFAULT_TILE_ATTRIBUTION;
