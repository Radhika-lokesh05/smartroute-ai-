import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { HospitalCard } from './HospitalCard';
import { HospitalNearbyItem } from '@/types/hospital';

describe('HospitalCard component', () => {
  const baseHospital: HospitalNearbyItem = {
    id: 'hosp-1',
    name: 'Apollo Emergency Center',
    lat: 12.9716,
    lng: 77.5946,
    phone: '+91-80-22223333',
    address: '154 Bannerghatta Road',
    eta_s: 480,
    distance_m: 3500,
    matches_type: true,
    simulated_beds: 24,
    beds_simulated: true,
    eta_estimated: false,
    route_geometry: null,
  };

  it('always renders the simulated beds count with an explicit "Simulated" badge', () => {
    render(<HospitalCard hospital={baseHospital} rank={1} />);

    expect(screen.getByText(/24 Beds/i)).toBeInTheDocument();
    expect(screen.getByText('Simulated')).toBeInTheDocument();
    // Verify it is never presented as live/real-time availability
    expect(screen.queryByText(/Live Available/i)).not.toBeInTheDocument();
  });

  it('renders a one-tap tel: link with the exact phone number', () => {
    render(<HospitalCard hospital={baseHospital} rank={1} />);

    const callLink = screen.getByRole('link', { name: /Call Apollo Emergency Center/i });
    expect(callLink).toBeInTheDocument();
    expect(callLink).toHaveAttribute('href', 'tel:+91-80-22223333');
  });

  it('renders "(estimated)" label when eta_estimated is true', () => {
    const estimatedHospital: HospitalNearbyItem = {
      ...baseHospital,
      eta_estimated: true,
    };
    render(<HospitalCard hospital={estimatedHospital} rank={2} />);

    expect(screen.getByText('(estimated)')).toBeInTheDocument();
  });

  it('renders "Does not list this specialty" warning when matches_type is false', () => {
    const mismatchHospital: HospitalNearbyItem = {
      ...baseHospital,
      matches_type: false,
    };
    render(<HospitalCard hospital={mismatchHospital} rank={3} />);

    expect(screen.getByText(/Does not list this specialty/i)).toBeInTheDocument();
  });

  it('triggers directions callback when Directions button is clicked', () => {
    const onDirections = vi.fn();
    render(<HospitalCard hospital={baseHospital} rank={1} onDirections={onDirections} />);

    const btn = screen.getByRole('button', { name: /Get directions to Apollo Emergency Center/i });
    fireEvent.click(btn);

    expect(onDirections).toHaveBeenCalledTimes(1);
    expect(onDirections).toHaveBeenCalledWith(baseHospital);
  });
});
