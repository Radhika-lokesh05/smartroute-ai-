import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useRouteImpactRefetch } from './useRouteImpactRefetch';

describe('useRouteImpactRefetch hook', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  it('debounces refetches by 3 seconds when multiple events arrive in flurry', () => {
    const refetchMock = vi.fn();
    const { result } = renderHook(() =>
      useRouteImpactRefetch({
        hasActiveRoute: true,
        refetchRoutes: refetchMock,
        debounceMs: 3000,
        throttleMs: 10000,
      })
    );

    // Event 1 at t=0
    act(() => {
      result.current.handleRouteImpact();
    });

    // Advance 1.5 seconds (less than 3s debounce)
    act(() => {
      vi.advanceTimersByTime(1500);
    });
    expect(refetchMock).not.toHaveBeenCalled();

    // Event 2 at t=1.5s
    act(() => {
      result.current.handleRouteImpact();
    });

    // Advance 2 seconds (total 3.5s, but only 2s since event 2)
    act(() => {
      vi.advanceTimersByTime(2000);
    });
    expect(refetchMock).not.toHaveBeenCalled();

    // Advance remaining 1.1s (total > 3s since event 2)
    act(() => {
      vi.advanceTimersByTime(1100);
    });
    expect(refetchMock).toHaveBeenCalledTimes(1);
  });

  it('throttles refetches to at most one per 10 seconds', () => {
    const refetchMock = vi.fn();
    const { result } = renderHook(() =>
      useRouteImpactRefetch({
        hasActiveRoute: true,
        refetchRoutes: refetchMock,
        debounceMs: 3000,
        throttleMs: 10000,
      })
    );

    // First trigger
    act(() => {
      result.current.handleRouteImpact();
    });
    act(() => {
      vi.advanceTimersByTime(3000); // 3s debounce resolves -> refetch 1 fires at t=3s
    });
    expect(refetchMock).toHaveBeenCalledTimes(1);

    // Second trigger at t=4s (only 1s after refetch 1 fired)
    act(() => {
      vi.advanceTimersByTime(1000);
      result.current.handleRouteImpact();
    });

    // Debounce 3s resolves at t=8s (only 5s after refetch 1, throttle is 10s)
    act(() => {
      vi.advanceTimersByTime(3000);
    });
    // Should NOT have fired yet because 10s haven't passed since t=3s
    expect(refetchMock).toHaveBeenCalledTimes(1);

    // Advance remaining 6s to reach t=14s (>= 10s since t=3s)
    act(() => {
      vi.advanceTimersByTime(6000);
    });
    expect(refetchMock).toHaveBeenCalledTimes(2);
  });

  it('does not trigger refetch if hasActiveRoute is false', () => {
    const refetchMock = vi.fn();
    const { result } = renderHook(() =>
      useRouteImpactRefetch({
        hasActiveRoute: false,
        refetchRoutes: refetchMock,
        debounceMs: 3000,
        throttleMs: 10000,
      })
    );

    act(() => {
      result.current.handleRouteImpact();
    });

    act(() => {
      vi.advanceTimersByTime(5000);
    });

    expect(refetchMock).not.toHaveBeenCalled();
  });
});
