import { UserRole } from '@/types/auth';
import { AmbulanceStatus } from '@/types/dispatch';

export interface AuditLogItem {
  id: string;
  actor_user_id?: string | null;
  action: string;
  entity_type: string;
  entity_id?: string | null;
  details?: Record<string, any> | null;
  created_at: string;
}

export interface AuditLogListResponse {
  items: AuditLogItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminUser {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface AdminUserListResponse {
  items: AdminUser[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminAmbulance {
  id: string;
  user_id: string;
  plate_number: string;
  status: AmbulanceStatus;
  is_verified: boolean;
  last_seen_at?: string | null;
  is_stale: boolean;
  user?: AdminUser | null;
}

export interface AdminAmbulanceListResponse {
  items: AdminAmbulance[];
  total: number;
  page: number;
  page_size: number;
}

export interface MetricsSummaryResponse {
  data_origin: 'all' | 'live' | 'simulated';
  days: number;
  incidents: {
    reported: number;
    validated: number;
    rejected_or_expired: number;
    resolved: number;
    validation_rate: number;
    report_to_validation_time_s: {
      median?: number | null;
      p90?: number | null;
    };
  };
  dispatches: {
    offered: number;
    accepted: number;
    declined: number;
    timed_out: number;
    acceptance_rate: number;
    manual_dispatches_needed: number;
    response_times_s: {
      validation_to_offer: { median?: number | null; p90?: number | null };
      offer_to_accept: { median?: number | null; p90?: number | null };
      accept_to_at_scene: { median?: number | null; p90?: number | null };
      at_scene_to_hospital: { median?: number | null; p90?: number | null };
      total_validation_to_at_scene: { median?: number | null; p90?: number | null };
    };
  };
  ambulances: {
    active_now: number;
    total_verified: number;
    average_availability: number;
  };
}

export interface TimeSeriesPoint {
  timestamp: string;
  incidents: number;
  dispatches: number;
}

export interface MetricsTimeseriesResponse {
  data_origin: string;
  days: number;
  bucket: 'hour' | 'day';
  points: TimeSeriesPoint[];
}

export interface HotspotCell {
  lat: number;
  lng: number;
  count: number;
  top_type: string;
}

export interface MetricsHotspotsResponse {
  data_origin: string;
  days: number;
  grid_m: number;
  total_cells: number;
  cells: HotspotCell[];
}

export interface ModelInfoResponse {
  model_available: boolean;
  model_version?: string;
  data_source?: string;
  dataset_name?: string;
  date_range?: string;
  model_mae?: number | null;
  model_r2?: number | null;
  baseline_mae?: number | null;
  baseline_r2?: number | null;
  model_beats_baseline?: boolean;
  mae_improvement_pct?: number;
  note?: string;
  error?: string;
}
