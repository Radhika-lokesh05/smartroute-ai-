import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { useState } from 'react';

import { RouteItem, RouteSummary } from '@/types/routing';
import { FasterRouteNotice } from './FasterRouteNotice';
import { RouteList } from './RouteList';

const sampleRoutes: RouteItem[] = [
  {
    distance_m: 5000,
    duration_s: 600,
    estimated_delay_s: 600, // delay on route 0
    adjusted_duration_s: 1200,
    avoids_incidents: false,
    rank: 2,
    reason: '+10 min delay',
    incidents_on_route: [],
    geometry: { type: 'LineString', coordinates: [] },
    steps: [],
  },
  {
    distance_m: 5500,
    duration_s: 700,
    estimated_delay_s: 0,
    adjusted_duration_s: 700,
    avoids_incidents: true,
    rank: 1, // Route 1 is recommended!
    reason: 'Avoids incidents',
    incidents_on_route: [],
    geometry: { type: 'LineString', coordinates: [] },
    steps: [],
  },
];

function TestHarness({
  initialSelectedIndex = 0,
  routes = sampleRoutes,
  summary = {
    incidents_considered: 1,
    fastest_raw_route_index: 0,
    recommended_route_index: 1,
    rerouted: true,
  } as RouteSummary,
}) {
  const [selectedIndex, setSelectedIndex] = useState(initialSelectedIndex);
  const [dismissed, setDismissed] = useState(false);

  const recommendedIdx = summary.recommended_route_index;
  const currentSelected = routes[selectedIndex];
  const recommendedRoute = routes[recommendedIdx];

  // Notice only appears if user selected a different, slower route
  const isFasterAvailable = Boolean(
    !dismissed &&
    routes.length > 1 &&
    selectedIndex !== recommendedIdx &&
    recommendedRoute &&
    currentSelected &&
    recommendedRoute.adjusted_duration_s < currentSelected.adjusted_duration_s
  );

  return (
    <div>
      <div data-testid="current-selected-index">{selectedIndex}</div>

      {isFasterAvailable && (
        <FasterRouteNotice
          isOpen={isFasterAvailable}
          savedSeconds={currentSelected.adjusted_duration_s - recommendedRoute.adjusted_duration_s}
          onSwitch={() => {
            setSelectedIndex(recommendedIdx);
            setDismissed(true);
          }}
          onDismiss={() => setDismissed(true)}
        />
      )}

      <RouteList
        routes={routes}
        selectedIndex={selectedIndex}
        onSelect={(idx) => setSelectedIndex(idx)}
        provider="openrouteservice"
      />
    </div>
  );
}

describe('Route Recommendation and Selection Flow', () => {
  it('selected route is NEVER changed automatically when recommendation changes', () => {
    // User had selected Route 0
    render(<TestHarness initialSelectedIndex={0} />);

    // The selected route remains Route 0
    expect(screen.getByTestId('current-selected-index')).toHaveTextContent('0');

    // The notice appears
    expect(screen.getByText('A faster route is available')).toBeInTheDocument();

    // Verify it still hasn't changed automatically
    expect(screen.getByTestId('current-selected-index')).toHaveTextContent('0');
  });

  it('notice only appears when the recommendation differs and is faster', () => {
    // If user is already on recommended route (index 1), notice must NOT appear
    render(<TestHarness initialSelectedIndex={1} />);

    expect(screen.queryByText('A faster route is available')).not.toBeInTheDocument();
  });

  it('switches to the recommended route ONLY when the user clicks Switch button', () => {
    render(<TestHarness initialSelectedIndex={0} />);

    expect(screen.getByTestId('current-selected-index')).toHaveTextContent('0');

    const switchBtn = screen.getByRole('button', { name: /switch/i });
    fireEvent.click(switchBtn);

    // Now selectedIndex updates to recommended index 1
    expect(screen.getByTestId('current-selected-index')).toHaveTextContent('1');
    // And notice disappears
    expect(screen.queryByText('A faster route is available')).not.toBeInTheDocument();
  });
});
