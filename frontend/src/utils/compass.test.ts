import { describe, it, expect } from 'vitest';
import { bearingToCompass, getRelativeBearing } from './compass';

describe('compass conversion and relative bearing utilities', () => {
  it('correctly maps 360-degree bearings to 8-point compass points', () => {
    expect(bearingToCompass(0)).toBe('N');
    expect(bearingToCompass(360)).toBe('N');
    expect(bearingToCompass(15)).toBe('N');
    expect(bearingToCompass(45)).toBe('NE');
    expect(bearingToCompass(90)).toBe('E');
    expect(bearingToCompass(135)).toBe('SE');
    expect(bearingToCompass(180)).toBe('S');
    expect(bearingToCompass(225)).toBe('SW');
    expect(bearingToCompass(270)).toBe('W');
    expect(bearingToCompass(315)).toBe('NW');
    expect(bearingToCompass(350)).toBe('N');
  });

  it('handles negative or overflow degrees smoothly', () => {
    expect(bearingToCompass(-90)).toBe('W');
    expect(bearingToCompass(450)).toBe('E');
  });

  it('calculates relative visual arrow bearing when user device heading is present', () => {
    // Ambulance bearing 90 (East), device heading 90 (East) -> Arrow points Straight Up (0 deg)
    expect(getRelativeBearing(90, 90)).toBe(0);

    // Ambulance bearing 180 (South), device heading 90 (East) -> Arrow points Right (90 deg)
    expect(getRelativeBearing(180, 90)).toBe(90);

    // Ambulance bearing 0 (North), device heading 90 (East) -> Arrow points Left (270 deg)
    expect(getRelativeBearing(0, 90)).toBe(270);
  });

  it('falls back to absolute bearing when device heading is null or NaN', () => {
    expect(getRelativeBearing(135, null)).toBe(135);
    expect(getRelativeBearing(220, undefined)).toBe(220);
    expect(getRelativeBearing(45, NaN)).toBe(45);
  });
});
