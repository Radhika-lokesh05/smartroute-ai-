/**
 * Coordinate conversion utilities between GeoJSON ([lng, lat]) and Leaflet ([lat, lng]).
 */

export type GeoJSONCoord = [number, number]; // [longitude, latitude]
export type LeafletCoord = [number, number]; // [latitude, longitude]

/**
 * Convert a single GeoJSON [lng, lat] coordinate pair to a Leaflet [lat, lng] pair.
 */
export function geojsonToLeaflet(coord: GeoJSONCoord): LeafletCoord {
  return [coord[1], coord[0]];
}

/**
 * Convert an array of GeoJSON [lng, lat] coordinates to Leaflet [lat, lng] coordinates.
 */
export function geojsonCoordsToLeaflet(coords: GeoJSONCoord[]): LeafletCoord[] {
  return coords.map((c) => [c[1], c[0]]);
}

/**
 * Convert a Leaflet [lat, lng] coordinate pair to a GeoJSON [lng, lat] pair.
 */
export function leafletToGeojson(coord: LeafletCoord): GeoJSONCoord {
  return [coord[1], coord[0]];
}

/**
 * Calculate the great-circle distance between two geographic coordinates in meters
 * using the Haversine formula (matching backend spatial calculation).
 */
export function calculateDistanceM(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371000.0; // Earth radius in meters
  const toRad = (deg: number) => (deg * Math.PI) / 180.0;
  const phi1 = toRad(lat1);
  const phi2 = toRad(lat2);
  const deltaPhi = toRad(lat2 - lat1);
  const deltaLambda = toRad(lon2 - lon1);

  const a =
    Math.sin(deltaPhi / 2.0) ** 2 +
    Math.cos(phi1) * Math.cos(phi2) * Math.sin(deltaLambda / 2.0) ** 2;
  const c = 2.0 * Math.atan2(Math.sqrt(a), Math.sqrt(1.0 - a));
  return R * c;
}
