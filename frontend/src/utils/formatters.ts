/**
 * Format distance in meters into readable format (e.g. 850m or 5.2 km).
 */
export function formatDistance(meters: number): string {
  if (meters < 1000) {
    return `${Math.round(meters)} m`;
  }
  return `${(meters / 1000).toFixed(1)} km`;
}

/**
 * Format duration in seconds into readable format (e.g. 14 min or 1 hr 25 min).
 */
export function formatDuration(seconds: number): string {
  const totalMinutes = Math.round(seconds / 60);
  if (totalMinutes < 1) {
    return '1 min';
  }
  if (totalMinutes < 60) {
    return `${totalMinutes} min`;
  }
  const hours = Math.floor(totalMinutes / 60);
  const remainingMins = totalMinutes % 60;
  if (remainingMins === 0) {
    return `${hours} hr`;
  }
  return `${hours} hr ${remainingMins} min`;
}

/**
 * Format incident remaining seconds into readable countdown format (e.g. 44m 30s, 45s, or Expired).
 */
export function formatCountdownSeconds(seconds: number): string {
  if (seconds <= 0) {
    return 'Expired';
  }
  const mins = Math.floor(seconds / 60);
  const remainingSecs = seconds % 60;
  if (mins === 0) {
    return `${remainingSecs}s`;
  }
  if (remainingSecs === 0) {
    return `${mins}m`;
  }
  return `${mins}m ${remainingSecs}s`;
}
