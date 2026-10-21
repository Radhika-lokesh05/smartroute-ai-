# API Route Permissions & Authentication Matrix

This document provides a comprehensive security audit of every API route and WebSocket endpoint within SmartRoute AI, documenting the required authentication level, role authorization checks, rate limiting policies, and data exposure safeguards.

## Route Permissions Table

| Method | Endpoint | Required Auth | Role Restriction | Rate Limit / Protection | Description |
|---|---|---|---|---|---|
| `GET` | `/` | None (Public) | None | Standard HTTP | Service info & health check pointers |
| `GET` | `/health` | None (Public) | None | Standard HTTP | Liveness probe (no database queries) |
| `GET` | `/ready` | None (Public) | None | Standard HTTP | Readiness probe (DB connectivity & model status) |
| `GET` | `/api/v1/health` | None (Public) | None | Standard HTTP | API v1 alias for liveness |
| `GET` | `/api/v1/ready` | None (Public) | None | Standard HTTP | API v1 alias for readiness |
| `POST` | `/api/auth/register` | None (Public) | Creates `civilian` | 10 per hour per IP | User registration with password strength checks |
| `POST` | `/api/auth/login` | None (Public) | Any active role | 5 / 15min per email, 20 / hr per IP | User login with constant-time check & JWT issuance |
| `POST` | `/api/auth/logout` | Authenticated | Any active role | User rate limit | Revokes token `jti` in token denylist |
| `GET` | `/api/auth/me` | Authenticated | Any active role | User rate limit | Returns authenticated user profile |
| `GET` | `/api/admin/audit` | Authenticated | `admin` only | User rate limit | Paginated audit trail of system administrative actions |
| `GET` | `/api/admin/users` | Authenticated | `admin` only | User rate limit | Search and inspect registered user accounts |
| `PATCH` | `/api/admin/users/{id}/active` | Authenticated | `admin` only | User rate limit | Deactivate or reactivate user (self-deactivation forbidden) |
| `GET` | `/api/admin/ambulances` | Authenticated | `admin` only | User rate limit | List registered ambulances with status |
| `POST` | `/api/admin/ambulances` | Authenticated | `admin` only | User rate limit | Create ambulance unit linked to user account |
| `PATCH` | `/api/admin/ambulances/{id}/verify` | Authenticated | `admin` only | User rate limit | Verify ambulance unit credentials |
| `PATCH` | `/api/admin/ambulances/{id}/unverify` | Authenticated | `admin` only | User rate limit | Revoke ambulance unit credentials |
| `POST` | `/api/admin/incidents/{id}/resolve` | Authenticated | `admin` only | User rate limit | Force-resolve an incident by administrative action |
| `POST` | `/api/admin/dispatches/manual` | Authenticated | `admin` only | User rate limit | Manually assign an emergency dispatch to an ambulance |
| `POST` | `/api/admin/dispatches/{id}/cancel` | Authenticated | `admin` only | User rate limit | Cancel active dispatch by administrator |
| `GET` | `/api/admin/dispatches` | Authenticated | `admin` only | User rate limit | Query dispatch historical logs |
| `GET` | `/api/admin/metrics/summary` | Authenticated | `admin` only | User rate limit | Aggregated platform metrics and SLA performance |
| `GET` | `/api/admin/metrics/timeseries` | Authenticated | `admin` only | User rate limit | Daily timeline metrics |
| `GET` | `/api/admin/metrics/hotspots` | Authenticated | `admin` only | User rate limit | PostGIS spatial aggregation grid for incident density |
| `GET` | `/api/admin/metrics/export.csv` | Authenticated | `admin` only | User rate limit | CSV data export with formula injection escaping & privacy redaction |
| `GET` | `/api/admin/model-info` | Authenticated | `admin` only | User rate limit | Traffic ML model metadata and feature importances |
| `GET` | `/api/geocode/autocomplete` | Authenticated | Any active role | 60 requests/min | Address autocomplete restricted to India |
| `GET` | `/api/geocode/search` | Authenticated | Any active role | 60 requests/min | Forward geocode search |
| `GET` | `/api/geocode/reverse` | Authenticated | Any active role | 60 requests/min | Reverse geocoding (coordinates to address) |
| `GET` | `/api/routes` | Authenticated | Any active role | 60 requests/min | Incident-aware route computation (GET query) |
| `POST` | `/api/routes` | Authenticated | Any active role | 60 requests/min | Incident-aware route computation (POST GeoJSON) |
| `POST` | `/api/incidents` | Authenticated | Any active role | 3 reports per 10min | Report incident with HTML sanitization & deduplication |
| `POST` | `/api/incidents/{incident_id}/vote` | Authenticated | Any active role | 30 votes per hour | Vote (confirm/reject) within physical proximity |
| `POST` | `/api/incidents/{incident_id}/resolve` | Authenticated | Reporter, ambulance, admin | User rate limit | Mark incident as resolved |
| `GET` | `/api/incidents/nearby` | Authenticated | Any active role | User rate limit | Query spatial incidents (sanitized, no user PII) |
| `GET` | `/api/incidents/{incident_id}` | Authenticated | Any active role | User rate limit | Inspect specific incident (no user PII) |
| `GET` | `/api/weather` | Authenticated | Any active role | User rate limit | Current weather from Open-Meteo |
| `POST` | `/api/traffic/predict` | Authenticated | Any active role | User rate limit | ML congestion factor prediction |
| `GET` | `/api/hospitals/nearby` | Authenticated | Any active role | User rate limit | Ranked emergency hospitals with incident penalties |
| `GET` | `/api/ambulance/me` | Authenticated | `ambulance` only | User rate limit | Return authenticated ambulance profile |
| `PATCH` | `/api/ambulance/status` | Authenticated | Verified `ambulance` | User rate limit | Update ambulance status (available/offline) |
| `POST` | `/api/dispatches/trigger` | Authenticated | `admin`, `ambulance` | User rate limit | Trigger dispatch to nearest verified ambulance |
| `POST` | `/api/dispatches/{id}/accept` | Authenticated | `ambulance` only | User rate limit | Accept dispatch offer |
| `POST` | `/api/dispatches/{id}/decline` | Authenticated | `ambulance` only | User rate limit | Decline dispatch offer with sanitized reason |
| `PATCH` | `/api/dispatches/{id}/progress` | Authenticated | `ambulance` only | User rate limit | Update dispatch state machine |
| `GET` | `/api/dispatches/active` | Authenticated | `admin`, `ambulance` | User rate limit | Get active emergency dispatches |
| `GET` | `/api/dispatches/{id}` | Authenticated | Any active role | User rate limit | Inspect dispatch record |
| `WS` | `/ws` | Authenticated | Any active role | 30 msgs / 5s, 16KB limit | Realtime spatial notifications & ambulance telemetry |

## Security Guarantees & Verification
1. **No Accidental Open Endpoints**: Every newly added route MUST be explicitly declared in the test suite `tests/test_route_permissions.py`. Any route missing an explicit security designation fails CI.
2. **Reverse Proxy Trust**: Client IP address resolution uses `TRUSTED_PROXY_HOPS` (default `1` in production) to prevent IP spoofing attacks on rate limiters.
3. **Sensitive Data Protection**: Passwords, tokens, API keys, and full database URLs are automatically redacted by the logging filter. Database credentials are never exposed in error responses.
