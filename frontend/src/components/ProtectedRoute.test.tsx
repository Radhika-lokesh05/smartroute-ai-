import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ProtectedRoute } from './ProtectedRoute';
import * as useAuthModule from '@/auth/useAuth';

vi.mock('@/auth/useAuth');

describe('ProtectedRoute component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading indicator while authentication state is resolving', () => {
    vi.spyOn(useAuthModule, 'useAuth').mockReturnValue({
      user: null,
      token: null,
      isLoading: true,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <div>Secret Protected Content</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText(/AUTHENTICATING/i)).toBeInTheDocument();
    expect(screen.queryByText('Secret Protected Content')).not.toBeInTheDocument();
  });

  it('redirects to /login when user is not authenticated', () => {
    vi.spyOn(useAuthModule, 'useAuth').mockReturnValue({
      user: null,
      token: null,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <div>Secret Protected Content</div>
              </ProtectedRoute>
            }
          />
          <Route path="/login" element={<div>Login Page Target</div>} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.queryByText('Secret Protected Content')).not.toBeInTheDocument();
    expect(screen.getByText('Login Page Target')).toBeInTheDocument();
  });

  it('renders children when user is authenticated', () => {
    vi.spyOn(useAuthModule, 'useAuth').mockReturnValue({
      user: {
        id: 'usr-123',
        name: 'Jane Doe',
        email: 'jane@example.com',
        role: 'civilian',
        is_active: true,
        created_at: '2026-01-01T00:00:00Z',
      },
      token: 'valid-jwt-token',
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <div>Secret Protected Content</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Secret Protected Content')).toBeInTheDocument();
  });

  it('redirects to / when user role is not in allowedRoles', () => {
    vi.spyOn(useAuthModule, 'useAuth').mockReturnValue({
      user: {
        id: 'usr-123',
        name: 'Jane Civilian',
        email: 'civilian@example.com',
        role: 'civilian',
        is_active: true,
        created_at: '2026-01-01T00:00:00Z',
      },
      token: 'valid-jwt-token',
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={['/ambulance']}>
        <Routes>
          <Route
            path="/ambulance"
            element={
              <ProtectedRoute allowedRoles={['ambulance']}>
                <div>Ambulance Only Console</div>
              </ProtectedRoute>
            }
          />
          <Route path="/" element={<div>Public Civilian Home</div>} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.queryByText('Ambulance Only Console')).not.toBeInTheDocument();
    expect(screen.getByText('Public Civilian Home')).toBeInTheDocument();
  });

  it('allows access when user role matches allowedRoles', () => {
    vi.spyOn(useAuthModule, 'useAuth').mockReturnValue({
      user: {
        id: 'usr-456',
        name: 'Medic John',
        email: 'medic@example.com',
        role: 'ambulance',
        is_active: true,
        created_at: '2026-01-01T00:00:00Z',
      },
      token: 'valid-jwt-token',
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={['/ambulance']}>
        <Routes>
          <Route
            path="/ambulance"
            element={
              <ProtectedRoute allowedRoles={['ambulance']}>
                <div>Ambulance Only Console</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Ambulance Only Console')).toBeInTheDocument();
  });
});
