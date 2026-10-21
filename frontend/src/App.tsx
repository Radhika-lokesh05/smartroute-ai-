import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from '@/auth/AuthContext';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { Login } from '@/pages/Login';
import { Register } from '@/pages/Register';
import { MapPage } from '@/pages/MapPage';
import { HospitalsPage } from '@/pages/HospitalsPage';
import { AmbulanceDashboard } from '@/pages/AmbulanceDashboard';
import { NotFoundPage } from '@/pages/NotFoundPage';
import { AdminLayout } from '@/components/admin/AdminLayout';
import { AdminOverviewPage } from '@/pages/admin/AdminOverviewPage';
import { AdminLiveMapPage } from '@/pages/admin/AdminLiveMapPage';
import { AdminDispatchesPage } from '@/pages/admin/AdminDispatchesPage';
import { AdminAmbulancesPage } from '@/pages/admin/AdminAmbulancesPage';
import { AdminUsersPage } from '@/pages/admin/AdminUsersPage';
import { AdminAuditPage } from '@/pages/admin/AdminAuditPage';
import { AdminModelPage } from '@/pages/admin/AdminModelPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

export const App: React.FC = () => {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <Router>
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route
                path="/"
                element={
                  <ProtectedRoute>
                    <MapPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/hospitals"
                element={
                  <ProtectedRoute>
                    <HospitalsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/ambulance"
                element={
                  <ProtectedRoute allowedRoles={['ambulance']}>
                    <AmbulanceDashboard />
                  </ProtectedRoute>
                }
              />

              {/* Admin Routes (Admin Role Only, Protected by Guard) */}
              <Route
                path="/admin"
                element={
                  <ProtectedRoute allowedRoles={['admin']}>
                    <AdminLayout />
                  </ProtectedRoute>
                }
              >
                <Route index element={<AdminOverviewPage />} />
                <Route path="map" element={<AdminLiveMapPage />} />
                <Route path="dispatches" element={<AdminDispatchesPage />} />
                <Route path="ambulances" element={<AdminAmbulancesPage />} />
                <Route path="users" element={<AdminUsersPage />} />
                <Route path="audit" element={<AdminAuditPage />} />
                <Route path="model" element={<AdminModelPage />} />
              </Route>

              {/* Catch-all 404 Route */}
              <Route path="*" element={<NotFoundPage />} />
            </Routes>
          </Router>
        </AuthProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
};

export default App;
