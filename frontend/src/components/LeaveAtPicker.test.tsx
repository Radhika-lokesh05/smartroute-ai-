import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { LeaveAtPicker } from './LeaveAtPicker';

describe('LeaveAtPicker component', () => {
  it('renders the "time of day not modelled" notice', () => {
    render(<LeaveAtPicker onChange={vi.fn()} />);

    const notice = screen.getByTestId('time-notice');
    expect(notice).toBeInTheDocument();
    expect(notice).toHaveTextContent(
      'Time of day is not modelled with this dataset. Predictions reflect the selected date\'s day of week, month and forecast weather.'
    );
  });

  it('toggles between "Leave now" and "Leave at..." and restricts input to 24h', () => {
    const handleChange = vi.fn();
    render(<LeaveAtPicker onChange={handleChange} />);

    // Initially in 'Leave now' mode, input is not in document
    expect(screen.queryByLabelText('Departure time input')).not.toBeInTheDocument();

    // Click "Leave at..."
    const leaveAtBtn = screen.getByRole('button', { name: /leave at/i });
    fireEvent.click(leaveAtBtn);

    // Input is now visible
    const input = screen.getByLabelText('Departure time input') as HTMLInputElement;
    expect(input).toBeInTheDocument();

    // Verify min and max bounds exist
    expect(input.min).toBeDefined();
    expect(input.max).toBeDefined();

    // Min and max difference should be approximately 24 hours
    const minTime = new Date(input.min).getTime();
    const maxTime = new Date(input.max).getTime();
    const diffHours = (maxTime - minTime) / (1000 * 60 * 60);
    expect(Math.round(diffHours)).toBe(24);

    // Click "Leave now" again
    const leaveNowBtn = screen.getByRole('button', { name: /leave now/i });
    fireEvent.click(leaveNowBtn);

    // Input is hidden and onChange is called with undefined
    expect(screen.queryByLabelText('Departure time input')).not.toBeInTheDocument();
    expect(handleChange).toHaveBeenCalledWith(undefined);
  });

  it('triggers onChange with ISO string when datetime input changes', () => {
    const handleChange = vi.fn();
    render(<LeaveAtPicker onChange={handleChange} />);

    fireEvent.click(screen.getByRole('button', { name: /leave at/i }));
    const input = screen.getByLabelText('Departure time input');

    // Change input value to a future date
    fireEvent.change(input, { target: { value: '2026-10-20T14:30' } });

    expect(handleChange).toHaveBeenCalled();
    const lastCallArg = handleChange.mock.calls[handleChange.mock.calls.length - 1][0];
    expect(typeof lastCallArg).toBe('string');
    expect(new Date(lastCallArg).toISOString()).toBe(lastCallArg);
  });
});
