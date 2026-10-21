import { describe, it, expect } from 'vitest';
import {
  geojsonToLeaflet,
  geojsonCoordsToLeaflet,
  leafletToGeojson,
  calculateDistanceM,
  GeoJSONCoord,
  LeafletCoord,
} from './coordinates';

describe('Coordinate Conversion Utilities', () => {
  it('correctly converts a single GeoJSON [lng, lat] to Leaflet [lat, lng]', () => {
    const geojson: GeoJSONCoord = [77.5946, 12.9716]; // Bengaluru: [lng, lat]
    const leaflet = geojsonToLeaflet(geojson);
    expect(leaflet).toEqual([12.9716, 77.5946]);
  });

  it('correctly converts an array of GeoJSON coordinates to Leaflet coordinates', () => {
    const geojsonArray: GeoJSONCoord[] = [
      [77.5946, 12.9716],
      [77.6245, 12.9352],
      [77.5806, 12.9784],
    ];
    const leafletArray = geojsonCoordsToLeaflet(geojsonArray);
    expect(leafletArray).toHaveLength(3);
    expect(leafletArray[0]).toEqual([12.9716, 77.5946]);
    expect(leafletArray[1]).toEqual([12.9352, 77.6245]);
    expect(leafletArray[2]).toEqual([12.9784, 77.5806]);
  });

  it('correctly converts a Leaflet [lat, lng] to GeoJSON [lng, lat]', () => {
    const leaflet: LeafletCoord = [12.9716, 77.5946];
    const geojson = leafletToGeojson(leaflet);
    expect(geojson).toEqual([77.5946, 12.9716]);
  });

  it('handles negative coordinates properly (e.g. Western/Southern hemispheres)', () => {
    const geojson: GeoJSONCoord = [-122.4194, 37.7749]; // San Francisco
    expect(geojsonToLeaflet(geojson)).toEqual([37.7749, -122.4194]);
    expect(leafletToGeojson([37.7749, -122.4194])).toEqual([-122.4194, 37.7749]);
  });

  it('calculates great-circle distance in meters accurately using calculateDistanceM', () => {
    // Distance to same point is 0
    expect(calculateDistanceM(12.9716, 77.5946, 12.9716, 77.5946)).toBeCloseTo(0, 1);

    // Distance between two points in Bengaluru (~1.1 km)
    const dist = calculateDistanceM(12.9716, 77.5946, 12.9816, 77.5946);
    expect(dist).toBeGreaterThan(1000);
    expect(dist).toBeLessThan(1200);
  });
});
