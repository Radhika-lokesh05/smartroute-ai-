export interface HealthResponse {
  status: string;
  service: string;
  database: 'connected' | 'unreachable' | string;
  database_detail?: string | null;
}
