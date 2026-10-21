import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { FasterRouteNotice } from './FasterRouteNotice';

describe('FasterRouteNotice component', () => {
  it('does not render when isOpen is false', () => {
    const { container } = render(
      <FasterRouteNotice
        isOpen={false}
        onSwitch={vi.fn()}
        onDismiss={vi.fn()}
      />
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders "A faster route is available" and "Switch" button when isOpen is true', () => {
    const onSwitch = vi.fn();
    const onDismiss = vi.fn();

    render(
      <FasterRouteNotice
        isOpen={true}
        onSwitch={onSwitch}
        onDismiss={onDismiss}
        savedSeconds={300} // 5 min
      />
    );

    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText('A faster route is available')).toBeInTheDocument();
    expect(screen.getByText(/Estimated ~5 min faster/i)).toBeInTheDocument();

    const switchBtn = screen.getByRole('button', { name: /switch/i });
    expect(switchBtn).toBeInTheDocument();

    fireEvent.click(switchBtn);
    expect(onSwitch).toHaveBeenCalledTimes(1);
  });

  it('handles dismiss when close button clicked', () => {
    const onDismiss = vi.fn();

    render(
      <FasterRouteNotice
        isOpen={true}
        onSwitch={vi.fn()}
        onDismiss={onDismiss}
      />
    );

    const closeBtn = screen.getByLabelText(/dismiss notice/i);
    fireEvent.click(closeBtn);
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });
});
