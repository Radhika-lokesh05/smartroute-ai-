import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RouteList } from './RouteList';
import { RouteItem } from '@/types/routing';

const mockRoutes: RouteItem[] = [
  {
    distance_m: 5400,
    duration_s: 720, // 12 min
    traffic_factor: 1.18,
    predicted_duration_s: 850,
    traffic_coverage: 0.85,
    estimated_delay_s: 240, // 4 min delay
    adjusted_duration_s: 1090, // ~18 min
    avoids_incidents: false,
    rank: 1,
    reason: 'Fastest route, ~18% slower than free-flow due to predicted traffic',
    incidents_on_route: [
      {
        id: 'inc-1',
        type: 'accident',
        status: 'validated',
        lat: 12.96,
        lng: 77.6,
        distance_from_route_m: 20,
      },
    ],
    geometry: { type: 'LineString', coordinates: [[77.59, 12.97], [77.62, 12.93]] },
    steps: [],
  },
  {
    distance_m: 6000,
    duration_s: 840,
    traffic_factor: 1.0,
    predicted_duration_s: 840,
    traffic_coverage: 1.0,
    estimated_delay_s: 0,
    adjusted_duration_s: 840,
    avoids_incidents: true,
    rank: 2,
    reason: 'Avoids reported incidents',
    incidents_on_route: [],
    geometry: { type: 'LineString', coordinates: [[77.59, 12.97], [77.63, 12.94]] },
    steps: [],
  },
];

describe('RouteList component', () => {
  it('renders main predicted/adjusted ETA and breakdown with traffic and incidents', () => {
    render(
      <RouteList
        routes={mockRoutes}
        selectedIndex={0}
        onSelect={vi.fn()}
        provider="openrouteservice"
      />
    );

    // Adjusted ETA (1090s = 18 min)
    expect(screen.getByText('18 min')).toBeInTheDocument();
    // Breakdown with free-flow, traffic, and incidents
    expect(screen.getByText('Free-flow: 12 min')).toBeInTheDocument();
    expect(screen.getByText('Traffic: +2 min')).toBeInTheDocument();
    expect(screen.getByText('Incidents: +4 min (estimated)')).toBeInTheDocument();
  });

  it('renders "+18% traffic" badge when traffic_factor > 1.05', () => {
    render(
      <RouteList
        routes={mockRoutes}
        selectedIndex={0}
        onSelect={vi.fn()}
        provider="openrouteservice"
      />
    );

    const trafficBadge = screen.getByTestId('traffic-badge');
    expect(trafficBadge).toBeInTheDocument();
    expect(trafficBadge).toHaveTextContent('+18% traffic');
  });

  it('renders coverage warning note when coverage < 1.0', () => {
    render(
      <RouteList
        routes={mockRoutes}
        selectedIndex={0}
        onSelect={vi.fn()}
        provider="openrouteservice"
      />
    );

    const coverageWarning = screen.getByTestId('coverage-warning');
    expect(coverageWarning).toBeInTheDocument();
    expect(coverageWarning).toHaveTextContent(
      'Traffic modeled for 85% of route (coverage limited to known Bengaluru corridors)'
    );
  });

  it('displays "Traffic model unavailable" badge when model_available is false', () => {
    render(
      <RouteList
        routes={mockRoutes}
        selectedIndex={0}
        onSelect={vi.fn()}
        provider="openrouteservice"
        traffic={{
          model_version: 'v1.0.0',
          data_source: 'kaggle',
          data_granularity: 'daily',
          time_of_day_modelled: false,
          model_available: false,
          weather: null,
        }}
      />
    );

    const unavailBadges = screen.getAllByTestId('model-unavailable-badge');
    expect(unavailBadges.length).toBeGreaterThan(0);
    expect(unavailBadges[0]).toHaveTextContent('Traffic model unavailable — showing free-flow times');
  });

  it('renders "Avoids incidents" badge on route avoiding incidents', () => {
    render(
      <RouteList
        routes={mockRoutes}
        selectedIndex={0}
        onSelect={vi.fn()}
        provider="openrouteservice"
      />
    );

    const avoidBadge = screen.getByTestId('avoid-badge');
    expect(avoidBadge).toBeInTheDocument();
    expect(avoidBadge).toHaveTextContent('Avoids incidents');
  });

  it('renders the human-readable route reasons', () => {
    render(
      <RouteList
        routes={mockRoutes}
        selectedIndex={0}
        onSelect={vi.fn()}
        provider="openrouteservice"
      />
    );

    expect(
      screen.getByText('Fastest route, ~18% slower than free-flow due to predicted traffic')
    ).toBeInTheDocument();
    expect(screen.getByText('Avoids reported incidents')).toBeInTheDocument();
  });
});
