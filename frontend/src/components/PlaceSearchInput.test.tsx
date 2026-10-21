import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { PlaceSearchInput } from './PlaceSearchInput';
import * as geocodeApi from '@/api/geocode';

vi.mock('@/api/geocode');

describe('PlaceSearchInput component', () => {
  const mockOnSelect = vi.fn();
  const mockOnChange = vi.fn();

  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('does NOT trigger autocomplete search if input has fewer than 3 characters', async () => {
    const spy = vi.spyOn(geocodeApi, 'fetchAutocomplete').mockResolvedValue({
      provider: 'openrouteservice',
      results: [],
    });

    const { rerender } = render(
      <PlaceSearchInput
        id="test-input"
        label="Test Search"
        value="m"
        onChange={mockOnChange}
        onSelect={mockOnSelect}
      />
    );

    act(() => {
      vi.advanceTimersByTime(500);
    });
    expect(spy).not.toHaveBeenCalled();

    rerender(
      <PlaceSearchInput
        id="test-input"
        label="Test Search"
        value="mg"
        onChange={mockOnChange}
        onSelect={mockOnSelect}
      />
    );

    act(() => {
      vi.advanceTimersByTime(500);
    });
    expect(spy).not.toHaveBeenCalled();
  });

  it('debounces the search request by 350ms for inputs with 3 or more characters', async () => {
    const spy = vi.spyOn(geocodeApi, 'fetchAutocomplete').mockResolvedValue({
      provider: 'openrouteservice',
      results: [
        {
          label: 'Koramangala, Bengaluru, Karnataka, India',
          lat: 12.9352,
          lng: 77.6245,
          locality: 'Bengaluru',
        },
      ],
    });

    const { rerender } = render(
      <PlaceSearchInput
        id="test-input"
        label="Test Search"
        value="kora"
        onChange={mockOnChange}
        onSelect={mockOnSelect}
      />
    );

    // Before 350ms, api should not have been called
    act(() => {
      vi.advanceTimersByTime(200);
    });
    expect(spy).not.toHaveBeenCalled();

    // Type more characters within the debounce window
    rerender(
      <PlaceSearchInput
        id="test-input"
        label="Test Search"
        value="koramangala"
        onChange={mockOnChange}
        onSelect={mockOnSelect}
      />
    );

    act(() => {
      vi.advanceTimersByTime(200);
    });
    expect(spy).not.toHaveBeenCalled();

    // Now advance past the 350ms debounce window
    await vi.advanceTimersByTimeAsync(200);

    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy).toHaveBeenCalledWith('koramangala', undefined, undefined, expect.any(AbortSignal));
  });

  it('renders autocomplete results and handles selection', async () => {
    vi.useRealTimers();
    vi.spyOn(geocodeApi, 'fetchAutocomplete').mockResolvedValue({
      provider: 'openrouteservice',
      results: [
        {
          label: 'Indiranagar, Bengaluru, Karnataka, India',
          lat: 12.9784,
          lng: 77.6408,
          locality: 'Bengaluru',
        },
      ],
    });

    render(
      <PlaceSearchInput
        id="test-input"
        label="Test Search"
        value="indiranagar"
        onChange={mockOnChange}
        onSelect={mockOnSelect}
      />
    );

    const option = await screen.findByRole('option', {}, { timeout: 1500 });
    expect(option).toBeInTheDocument();
    expect(screen.getByText('Indiranagar, Bengaluru, Karnataka, India')).toBeInTheDocument();

    fireEvent.click(option);
    expect(mockOnSelect).toHaveBeenCalledWith(
      expect.objectContaining({
        label: 'Indiranagar, Bengaluru, Karnataka, India',
        lat: 12.9784,
        lng: 77.6408,
      })
    );
  });
});
