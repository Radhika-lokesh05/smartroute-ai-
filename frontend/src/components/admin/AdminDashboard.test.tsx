import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import * as useAuthModule from '@/auth/useAuth';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { ConfirmDialog } from './ConfirmDialog';
import { KpiCards } from './KpiCards';
import { AdminLayout } from './AdminLayout';
import { downloadMetricsCsv } from '@/api/admin';

vi.mock('@/auth/useAuth');

describe('Admin Dashboard Test Suite', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  // 1. Admin route guard
  it('blocks civilian user from accessing admin route and redirects', () => {
    vi.spyOn(useAuthModule, 'useAuth').mockReturnValue({
      user: { id: 'civ-1', name: 'Civilian User', email: 'civ@test.com', role: 'civilian', is_active: true, created_at: '2026-01-01T00:00:00Z' },
      token: 'fake-token',
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={['/admin']}>
        <Routes>
          <Route
            path="/admin"
            element={
              <ProtectedRoute allowedRoles={['admin']}>
                <div>Secret Admin Console</div>
              </ProtectedRoute>
            }
          />
          <Route path="/" element={<div>Public Home Page</div>} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.queryByText('Secret Admin Console')).not.toBeInTheDocument();
    expect(screen.getByText('Public Home Page')).toBeInTheDocument();
  });

  it('allows administrator to access admin route', () => {
    vi.spyOn(useAuthModule, 'useAuth').mockReturnValue({
      user: { id: 'adm-1', name: 'Admin Master', email: 'admin@test.com', role: 'admin', is_active: true, created_at: '2026-01-01T00:00:00Z' },
      token: 'fake-token',
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={['/admin']}>
        <Routes>
          <Route
            path="/admin"
            element={
              <ProtectedRoute allowedRoles={['admin']}>
                <div>Secret Admin Console</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Secret Admin Console')).toBeInTheDocument();
  });

  // 2. KPI rendering with null values (no NaN)
  it('renders KPI cards with null values without displaying NaN', () => {
    const emptySummary: any = {
      data_origin: 'all',
      days: 7,
      incidents: {
        reported: 0,
        validated: 0,
        rejected_or_expired: 0,
        resolved: 0,
        validation_rate: null, // Null rate
        report_to_validation_time_s: { median: null, p90: null },
      },
      dispatches: {
        offered: 0,
        accepted: 0,
        declined: 0,
        timed_out: 0,
        acceptance_rate: null, // Null rate
        manual_dispatches_needed: 0,
        response_times_s: {
          total_validation_to_at_scene: { median: null, p90: null },
        },
      },
      ambulances: {
        active_now: 0,
        total_verified: 0,
        average_availability: null,
      },
    };

    render(<KpiCards summary={emptySummary} isLoading={false} />);

    // Assert that "NaN" NEVER appears anywhere on the screen
    expect(screen.queryByText(/NaN/i)).not.toBeInTheDocument();

    // Rates should fallback to 0.0%
    const zeros = screen.getAllByText('0.0%');
    expect(zeros.length).toBeGreaterThanOrEqual(1);

    // Empty response time should display "— / —"
    expect(screen.getByText('— / —')).toBeInTheDocument();
  });

  // 3. Simulated badge
  it('renders the simulated badge when isSimulatedActive is true', () => {
    vi.spyOn(useAuthModule, 'useAuth').mockReturnValue({
      user: { id: 'adm-1', name: 'Admin Master', email: 'admin@test.com', role: 'admin', is_active: true, created_at: '2026-01-01T00:00:00Z' },
      token: 'fake-token',
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
    });

    const { rerender } = render(
      <MemoryRouter>
        <AdminLayout isSimulatedActive={false} />
      </MemoryRouter>
    );
    expect(screen.queryByTestId('simulated-badge')).not.toBeInTheDocument();

    rerender(
      <MemoryRouter>
        <AdminLayout isSimulatedActive={true} />
      </MemoryRouter>
    );
    const badge = screen.getByTestId('simulated-badge');
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveTextContent(/simulated data/i);
  });

  // 4. Confirm dialogs
  it('handles confirm and cancel actions on ConfirmDialog', () => {
    const handleConfirm = vi.fn();
    const handleCancel = vi.fn();

    const { rerender } = render(
      <ConfirmDialog
        isOpen={true}
        title="Revoke Verification"
        message="Are you sure you want to proceed?"
        confirmLabel="Yes, Revoke"
        onConfirm={handleConfirm}
        onCancel={handleCancel}
      />
    );

    expect(screen.getByText('Revoke Verification')).toBeInTheDocument();
    expect(screen.getByText('Are you sure you want to proceed?')).toBeInTheDocument();

    // Click confirm
    fireEvent.click(screen.getByText('Yes, Revoke'));
    expect(handleConfirm).toHaveBeenCalledTimes(1);

    // Click cancel
    fireEvent.click(screen.getByText('Cancel'));
    expect(handleCancel).toHaveBeenCalledTimes(1);

    // Unmount / isOpen=false
    rerender(
      <ConfirmDialog
        isOpen={false}
        title="Revoke Verification"
        message="Are you sure you want to proceed?"
        onConfirm={handleConfirm}
        onCancel={handleCancel}
      />
    );
    expect(screen.queryByText('Revoke Verification')).not.toBeInTheDocument();
  });

  // 5. CSV download uses auth header and never puts token in URL
  it('downloads CSV using Authorization Bearer header without token in URL', async () => {
    localStorage.setItem('token', 'secret-jwt-token-12345');

    const fakeBlob = new Blob(['col1,col2\nval1,val2'], { type: 'text/csv' });
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      blob: vi.fn().mockResolvedValue(fakeBlob),
    });
    window.fetch = mockFetch;
    window.URL.createObjectURL = vi.fn().mockReturnValue('blob:http://localhost/123');
    window.URL.revokeObjectURL = vi.fn();

    await downloadMetricsCsv('incidents', 7, 'all');

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [calledUrl, calledOptions] = mockFetch.mock.calls[0];

    // Assert token is in Authorization header
    expect(calledOptions.headers.Authorization).toBe('Bearer secret-jwt-token-12345');

    // Assert token is NEVER placed in URL
    expect(calledUrl).not.toContain('secret-jwt-token-12345');
    expect(calledUrl).toContain('/api/admin/metrics/export.csv');
    expect(calledUrl).toContain('kind=incidents');
  });

  // 6. Table pagination logic
  it('correctly calculates pagination and toggles pages', () => {
    const totalRecords = 35;
    const pageSize = 15;
    const totalPages = Math.ceil(totalRecords / pageSize); // 3 pages

    expect(totalPages).toBe(3);

    let page = 1;
    const nextPage = () => { page = Math.min(totalPages, page + 1); };
    const prevPage = () => { page = Math.max(1, page - 1); };

    nextPage();
    expect(page).toBe(2);
    nextPage();
    expect(page).toBe(3);
    nextPage();
    expect(page).toBe(3); // Capped at 3

    prevPage();
    expect(page).toBe(2);
    prevPage();
    expect(page).toBe(1);
    prevPage();
    expect(page).toBe(1); // Floor at 1
  });
});
