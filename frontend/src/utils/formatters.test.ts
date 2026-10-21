import { describe, it, expect } from 'vitest';
import { formatDistance, formatDuration, formatCountdownSeconds } from './formatters';

describe('Formatter Utilities', () => {
  describe('formatDistance', () => {
    it('formats distances less than 1000 meters as meters', () => {
      expect(formatDistance(0)).toBe('0 m');
      expect(formatDistance(450)).toBe('450 m');
      expect(formatDistance(999)).toBe('999 m');
    });

    it('formats distances 1000 meters and above as kilometers with 1 decimal place', () => {
      expect(formatDistance(1000)).toBe('1.0 km');
      expect(formatDistance(1250)).toBe('1.3 km');
      expect(formatDistance(5200)).toBe('5.2 km');
      expect(formatDistance(24890)).toBe('24.9 km');
    });
  });

  describe('formatDuration', () => {
    it('formats durations less than 60 seconds as 1 min', () => {
      expect(formatDuration(0)).toBe('1 min');
      expect(formatDuration(25)).toBe('1 min');
    });

    it('formats minutes under 1 hour correctly', () => {
      expect(formatDuration(60)).toBe('1 min');
      expect(formatDuration(840)).toBe('14 min');
      expect(formatDuration(3540)).toBe('59 min');
    });

    it('formats exact hours without remaining minutes', () => {
      expect(formatDuration(3600)).toBe('1 hr');
      expect(formatDuration(7200)).toBe('2 hr');
    });

    it('formats hours with remaining minutes', () => {
      expect(formatDuration(5100)).toBe('1 hr 25 min'); // 85 min = 1h 25m
      expect(formatDuration(11400)).toBe('3 hr 10 min'); // 190 min = 3h 10m
    });
  });

  describe('formatCountdownSeconds', () => {
    it('returns Expired for zero or negative seconds', () => {
      expect(formatCountdownSeconds(0)).toBe('Expired');
      expect(formatCountdownSeconds(-15)).toBe('Expired');
    });

    it('formats seconds less than 60 as seconds', () => {
      expect(formatCountdownSeconds(45)).toBe('45s');
      expect(formatCountdownSeconds(1)).toBe('1s');
    });

    it('formats minutes and seconds correctly', () => {
      expect(formatCountdownSeconds(60)).toBe('1m');
      expect(formatCountdownSeconds(125)).toBe('2m 5s');
      expect(formatCountdownSeconds(2670)).toBe('44m 30s');
    });
  });
});
