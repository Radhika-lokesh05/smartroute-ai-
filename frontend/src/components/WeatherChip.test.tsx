import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { WeatherChip } from './WeatherChip';
import { WeatherInfo } from '@/types/routing';

describe('WeatherChip component', () => {
  it('renders weather condition and temperature', () => {
    const weather: WeatherInfo = {
      condition: 'Rain',
      precipitation_mm: 3.5,
      visibility_m: 6000,
      temperature_c: 22.4,
    };

    render(<WeatherChip weather={weather} />);

    const chip = screen.getByTestId('weather-chip');
    expect(chip).toBeInTheDocument();
    expect(screen.getByText('Rain')).toBeInTheDocument();
    expect(screen.getByText(', 22°C')).toBeInTheDocument();
    expect(screen.getByText('🌧️')).toBeInTheDocument();
  });

  it('contains tooltip with precipitation and visibility', () => {
    const weather: WeatherInfo = {
      condition: 'Clear',
      precipitation_mm: 0.0,
      visibility_m: 10000,
      temperature_c: 28.0,
    };

    render(<WeatherChip weather={weather} />);

    const chip = screen.getByTestId('weather-chip');
    expect(chip).toHaveAttribute('title', 'Precipitation: 0.0 mm | Visibility: 10.0 km');
  });

  it('renders nothing when weather is null or undefined', () => {
    const { container } = render(<WeatherChip weather={null} />);
    expect(container.firstChild).toBeNull();
  });
});
