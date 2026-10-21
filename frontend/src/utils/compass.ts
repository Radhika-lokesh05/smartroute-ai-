/**
 * Compass conversion and relative bearing utilities.
 */

const COMPASS_POINTS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'] as const;

/**
 * Convert a great-circle bearing in degrees [0, 360) to 8-point compass notation.
 */
export function bearingToCompass(deg: number): string {
  const normalized = ((deg % 360) + 360) % 360;
  const index = Math.round(normalized / 45) % 8;
  return COMPASS_POINTS[index];
}

/**
 * Calculate relative visual arrow rotation angle taking user device heading into account.
 * Returns angle in degrees [0, 360).
 */
export function getRelativeBearing(bearingDeg: number, headingDeg?: number | null): number {
  if (headingDeg == null || Number.isNaN(headingDeg)) {
    return ((bearingDeg % 360) + 360) % 360;
  }
  return ((bearingDeg - headingDeg + 360) % 360 + 360) % 360;
}
