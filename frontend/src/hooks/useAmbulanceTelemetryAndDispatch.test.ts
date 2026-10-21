import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useAmbulanceTelemetry } from './useAmbulanceTelemetry';
import { useAmbulanceDispatch } from './useAmbulanceDispatch';
import * as dispatchApi from '@/api/dispatch';

vi.mock('@/api/dispatch');

describe('Ambulance Telemetry & Dispatch hooks', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('useAmbulanceTelemetry', () => {
    let watchCallback: (pos: any) => void;
    let clearWatchMock: any;

    beforeEach(() => {
      clearWatchMock = vi.fn();
      vi.stubGlobal('navigator', {
        ...globalThis.navigator,
        geolocation: {
          watchPosition: vi.fn((cb) => {
            watchCallback = cb;
            return 42; // watch id
          }),
          clearWatch: clearWatchMock,
        },
      });
    });

    afterEach(() => {
      vi.unstubAllGlobals();
    });

    it('throttles location updates and sends through RealtimeClient at 2-second minimum interval', () => {
      const mockClient = {
        sendLocation: vi.fn(),
      } as any;

      const { result, unmount } = renderHook(() =>
        useAmbulanceTelemetry({
          initialStatus: 'available',
          realtimeClient: mockClient,
        })
      );

      // First GPS update -> sent immediately
      act(() => {
        watchCallback({
          coords: {
            latitude: 12.9716,
            longitude: 77.5946,
            accuracy: 10,
            heading: 90,
            speed: 10,
          },
        });
      });

      expect(mockClient.sendLocation).toHaveBeenCalledTimes(1);
      expect(mockClient.sendLocation).toHaveBeenCalledWith(12.9716, 77.5946, 90, 36);

      // Rapid second GPS update within 500ms (< 2000ms minimum interval) -> dropped
      act(() => {
        watchCallback({
          coords: {
            latitude: 12.9720,
            longitude: 77.5950,
            accuracy: 8,
            heading: 90,
            speed: 12,
          },
        });
      });

      expect(mockClient.sendLocation).toHaveBeenCalledTimes(1); // not called again
      expect(result.current.coords?.lat).toBe(12.9720); // local coords updated
      unmount();
    });

    it('stops GPS tracking when status transitions to offline', async () => {
      vi.spyOn(dispatchApi, 'setAmbulanceStatus').mockResolvedValue({
        id: 'amb-1',
        user_id: 'usr-1',
        plate_number: 'KA-01-A-1111',
        status: 'offline',
        is_verified: true,
      });

      const { result, unmount } = renderHook(() =>
        useAmbulanceTelemetry({
          initialStatus: 'available',
        })
      );

      await act(async () => {
        await result.current.updateStatus('offline');
      });

      expect(clearWatchMock).toHaveBeenCalledWith(42);
      expect(result.current.status).toBe('offline');
      unmount();
    });
  });

  describe('useAmbulanceDispatch reconnect rebuild', () => {
    it('calls getCurrentDispatch on mount to restore active dispatch on page refresh', async () => {
      const mockDispatch = {
        id: 'disp-active-1',
        incident_id: 'inc-1',
        ambulance_id: 'amb-1',
        hospital_id: null,
        status: 'en_route_to_scene',
        offered_at: '2026-01-01T00:00:00Z',
        accepted_at: '2026-01-01T00:01:00Z',
        arrived_at: null,
        picked_up_at: null,
        completed_at: null,
        eta_to_scene_s: 240,
        eta_to_hospital_s: 600,
        emergency_type: 'trauma',
        offer_number: 1,
      } as any;

      vi.spyOn(dispatchApi, 'getCurrentDispatch').mockResolvedValue(mockDispatch);

      const { result } = renderHook(() =>
        useAmbulanceDispatch({})
      );

      // Wait for initial async effect
      await act(async () => {});

      expect(dispatchApi.getCurrentDispatch).toHaveBeenCalledTimes(1);
      expect(result.current.activeDispatch?.id).toBe('disp-active-1');
      expect(result.current.activeDispatch?.status).toBe('en_route_to_scene');
    });
  });
});
