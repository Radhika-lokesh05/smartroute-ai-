import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { UnverifiedAmbulanceScreen } from './UnverifiedAmbulanceScreen';
import { DispatchOfferModal } from './DispatchOfferModal';
import { DispatchStepper } from './DispatchStepper';
import { AmbulanceWarningBanner } from './AmbulanceWarningBanner';
import { MOVE_ASIDE_INSTRUCTION } from '@/constants/trafficRules';
import { DispatchOfferData } from '@/types/dispatch';

describe('Ambulance Dashboard & Warning features', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  // 1. Unverified ambulance screen
  describe('UnverifiedAmbulanceScreen', () => {
    it('renders awaiting admin verification holding screen and triggers refresh', () => {
      const onRefresh = vi.fn();
      render(<UnverifiedAmbulanceScreen plateNumber="KA-01-EA-1234" onRefresh={onRefresh} />);

      expect(screen.getByText(/Awaiting Admin Verification/i)).toBeInTheDocument();
      expect(screen.getByText('(KA-01-EA-1234)')).toBeInTheDocument();

      const btn = screen.getByRole('button', { name: /Re-check Verification/i });
      fireEvent.click(btn);
      expect(onRefresh).toHaveBeenCalledTimes(1);
    });
  });

  // 2. Offer countdown and expiry handling
  describe('DispatchOfferModal', () => {
    const mockOffer: DispatchOfferData = {
      dispatch_id: 'disp-999',
      incident_id: 'inc-123',
      emergency_type: 'cardiac',
      incident_lat: 12.9716,
      incident_lng: 77.5946,
      eta_to_scene_s: 180,
      expires_in_s: 60,
    };

    it('renders countdown, incident details, and calls onExpire when timer elapses', () => {
      const onAccept = vi.fn().mockResolvedValue(undefined);
      const onDecline = vi.fn().mockResolvedValue(undefined);
      const onExpire = vi.fn();

      render(
        <DispatchOfferModal
          offer={mockOffer}
          onAccept={onAccept}
          onDecline={onDecline}
          onExpire={onExpire}
        />
      );

      expect(screen.getByText('00:60')).toBeInTheDocument();
      expect(screen.getByText(/cardiac/i)).toBeInTheDocument();

      // Advance timers by 10s
      act(() => {
        vi.advanceTimersByTime(10000);
      });
      expect(screen.getByText('00:50')).toBeInTheDocument();

      // Advance remaining 50s
      act(() => {
        vi.advanceTimersByTime(50000);
      });
      expect(onExpire).toHaveBeenCalledTimes(1);
    });

    it('disables buttons when submitting', () => {
      render(
        <DispatchOfferModal
          offer={mockOffer}
          onAccept={vi.fn()}
          onDecline={vi.fn()}
          onExpire={vi.fn()}
          isSubmitting={true}
        />
      );

      const acceptBtn = screen.getByRole('button', { name: /Accepting/i });
      const declineBtn = screen.getByRole('button', { name: /Decline/i });

      expect(acceptBtn).toBeDisabled();
      expect(declineBtn).toBeDisabled();
    });
  });

  // 3. State stepper only offers the next valid action
  describe('DispatchStepper', () => {
    it('offers strictly "Arrive at Scene" when en_route_to_scene', () => {
      const onAdvance = vi.fn();
      render(<DispatchStepper currentStatus="en_route_to_scene" onAdvance={onAdvance} />);

      const nextBtn = screen.getByRole('button', { name: /Arrive at Scene/i });
      expect(nextBtn).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Transport to Hospital/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Complete Mission/i })).not.toBeInTheDocument();

      fireEvent.click(nextBtn);
      expect(onAdvance).toHaveBeenCalledWith('at_scene');
    });

    it('offers strictly "Transport to Hospital" when at_scene', () => {
      const onAdvance = vi.fn();
      render(<DispatchStepper currentStatus="at_scene" onAdvance={onAdvance} />);

      const nextBtn = screen.getByRole('button', { name: /Transport to Hospital/i });
      expect(nextBtn).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Arrive at Scene/i })).not.toBeInTheDocument();

      fireEvent.click(nextBtn);
      expect(onAdvance).toHaveBeenCalledWith('to_hospital');
    });

    it('prompts for confirmation before completing dispatch when to_hospital', () => {
      const onAdvance = vi.fn();
      render(<DispatchStepper currentStatus="to_hospital" onAdvance={onAdvance} />);

      const completeBtn = screen.getByRole('button', { name: /Complete Mission/i });
      fireEvent.click(completeBtn);

      // Verify confirmation dialog appears
      expect(screen.getByText(/Confirm mission completion/i)).toBeInTheDocument();

      const confirmBtn = screen.getByRole('button', { name: /Yes, Complete/i });
      fireEvent.click(confirmBtn);
      expect(onAdvance).toHaveBeenCalledWith('completed');
    });
  });

  // 4. Warning banner show / hide / dedupe & no ambulance identity
  describe('AmbulanceWarningBanner', () => {
    it('displays approaching alert with configured road safety instructions', () => {
      const onDismiss = vi.fn();
      render(
        <AmbulanceWarningBanner
          warning={{
            distance_m: 450,
            bearing_deg: 180,
            approaching: true,
            expires_in_s: 10,
            received_at: Date.now(),
          }}
          onDismiss={onDismiss}
        />
      );

      const alert = screen.getByRole('alert');
      expect(alert).toHaveAttribute('aria-live', 'assertive');
      expect(alert).toHaveTextContent(`Ambulance approaching, about 450m away, ${MOVE_ASIDE_INSTRUCTION}.`);
      expect(screen.getByText('S')).toBeInTheDocument(); // 180 deg = S
    });

    it('displays softer nearby notice when approaching is false', () => {
      render(
        <AmbulanceWarningBanner
          warning={{
            distance_m: 800,
            bearing_deg: 90,
            approaching: false,
            expires_in_s: 10,
            received_at: Date.now(),
          }}
          onDismiss={vi.fn()}
        />
      );

      expect(screen.getByText(/Ambulance nearby, about 800m away/i)).toBeInTheDocument();
      expect(screen.queryByText(MOVE_ASIDE_INSTRUCTION)).not.toBeInTheDocument();
      expect(screen.getByText('E')).toBeInTheDocument(); // 90 deg = E
    });

    it('strictly does NOT render any ambulance identity, plate number, or driver fields', () => {
      const { container } = render(
        <AmbulanceWarningBanner
          warning={{
            distance_m: 500,
            bearing_deg: 0,
            approaching: true,
            expires_in_s: 10,
            received_at: Date.now(),
          }}
          onDismiss={vi.fn()}
        />
      );

      const html = container.innerHTML.toLowerCase();
      expect(html).not.toContain('plate');
      expect(html).not.toContain('driver');
      expect(html).not.toContain('ambulance_id');
      expect(html).not.toContain('vehicle_id');
    });
  });
});
