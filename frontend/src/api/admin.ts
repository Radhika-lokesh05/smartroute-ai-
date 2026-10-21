import { apiClient, API_BASE_URL } from '@/api/client';
import {
  AdminAmbulanceListResponse,
  AdminUser,
  AdminUserListResponse,
  AuditLogListResponse,
  MetricsHotspotsResponse,
  MetricsSummaryResponse,
  MetricsTimeseriesResponse,
  ModelInfoResponse,
} from '@/types/admin';
import { DispatchResponse } from '@/types/dispatch';

export async function getAdminUsers(params: {
  search?: string;
  role?: string;
  page?: number;
  page_size?: number;
}): Promise<AdminUserListResponse> {
  const res = await apiClient.get<AdminUserListResponse>('/api/admin/users', { params });
  return res.data;
}

export async function toggleUserActive(userId: string, isActive: boolean): Promise<AdminUser> {
  const res = await apiClient.patch<AdminUser>(`/api/admin/users/${userId}/active`, {
    is_active: isActive,
  });
  return res.data;
}

export async function getAdminAmbulances(params: {
  status?: string;
  is_verified?: boolean;
  page?: number;
  page_size?: number;
}): Promise<AdminAmbulanceListResponse> {
  const res = await apiClient.get<AdminAmbulanceListResponse>('/api/admin/ambulances', { params });
  return res.data;
}

export async function unverifyAmbulance(id: string): Promise<any> {
  const res = await apiClient.patch(`/api/admin/ambulances/${id}/unverify`);
  return res.data;
}

export async function verifyAmbulance(id: string): Promise<any> {
  const res = await apiClient.patch(`/api/admin/ambulances/${id}/verify`, { is_verified: true });
  return res.data;
}

export async function forceResolveIncident(id: string, reason?: string): Promise<any> {
  const res = await apiClient.post(`/api/admin/incidents/${id}/resolve`, { reason });
  return res.data;
}

export async function manualAssignDispatch(data: {
  incident_id: string;
  ambulance_id: string;
  emergency_type?: string;
}): Promise<DispatchResponse> {
  const res = await apiClient.post<DispatchResponse>('/api/admin/dispatches/manual', data);
  return res.data;
}

export async function cancelDispatch(dispatchId: string, reason?: string): Promise<any> {
  const res = await apiClient.post(`/api/admin/dispatches/${dispatchId}/cancel`, { reason });
  return res.data;
}

export async function getAdminDispatches(params: {
  status?: string;
  page?: number;
  page_size?: number;
}): Promise<{ items: DispatchResponse[]; total: number; page: number; page_size: number }> {
  const res = await apiClient.get('/api/admin/dispatches', { params });
  return res.data;
}

export async function getAuditLogs(params: {
  action?: string;
  start_date?: string;
  end_date?: string;
  page?: number;
  page_size?: number;
}): Promise<AuditLogListResponse> {
  const res = await apiClient.get<AuditLogListResponse>('/api/admin/audit', { params });
  return res.data;
}

export async function getMetricsSummary(days: number = 7, origin: string = 'all'): Promise<MetricsSummaryResponse> {
  const res = await apiClient.get<MetricsSummaryResponse>('/api/admin/metrics/summary', {
    params: { days, origin },
  });
  return res.data;
}

export async function getMetricsTimeseries(
  days: number = 7,
  bucket: 'hour' | 'day' = 'day',
  origin: string = 'all'
): Promise<MetricsTimeseriesResponse> {
  const res = await apiClient.get<MetricsTimeseriesResponse>('/api/admin/metrics/timeseries', {
    params: { days, bucket, origin },
  });
  return res.data;
}

export async function getMetricsHotspots(days: number = 7, origin: string = 'all'): Promise<MetricsHotspotsResponse> {
  const res = await apiClient.get<MetricsHotspotsResponse>('/api/admin/metrics/hotspots', {
    params: { days, origin },
  });
  return res.data;
}

export async function getModelInfo(): Promise<ModelInfoResponse> {
  const res = await apiClient.get<ModelInfoResponse>('/api/admin/model-info');
  return res.data;
}

export async function downloadMetricsCsv(
  kind: 'incidents' | 'dispatches',
  days: number = 7,
  origin: string = 'all'
): Promise<void> {
  const token = localStorage.getItem('token');
  const response = await fetch(
    `${API_BASE_URL}/api/admin/metrics/export.csv?kind=${kind}&days=${days}&origin=${origin}`,
    {
      headers: {
        Authorization: `Bearer ${token || ''}`,
      },
    }
  );
  if (!response.ok) {
    throw new Error(`CSV download failed with status ${response.status}`);
  }
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${kind}_${days}d_${origin}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
}
