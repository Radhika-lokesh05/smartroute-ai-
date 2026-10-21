# Security Architecture and Hardening Guide

This document describes the security posture, defensive configurations, and audit procedures implemented across the SmartRoute AI backend and frontend.

---

## 1. Environment & Startup Hardening
The application distinguishes between `development` and `production` via the `ENV` environment variable.
In production (`ENV=production`), the backend validates its configuration during startup and **refuses to start** if any insecure configuration is detected:
- **`JWT_SECRET`**: Must be configured, at least 32 characters in length, and cannot equal or contain known placeholder values from template files.
- **`ALLOWED_ORIGINS`**: Wildcards (`"*"`) are strictly forbidden; non-localhost HTTP origins (`http://...`) are rejected to enforce HTTPS.
- **`DATABASE_URL`**: Must point to an actual PostgreSQL instance; placeholder URLs are rejected.
- **Startup Errors**: Startup validation errors are logged cleanly without ever printing or echoing secret keys or database credentials.

---

## 2. API Documentation Security
In production mode:
- Interactive API documentation (`/docs`, `/redoc`, and `/openapi.json`) is **disabled** (`docs_url=None`, `redoc_url=None`, `openapi_url=None`).
- Internal endpoints and schema specifications are not exposed to public scraping or reconnaissance.

---

## 3. Reverse Proxy & Client IP Handling
SmartRoute AI runs behind a reverse proxy (e.g., Render's Cloudflare-powered routing edge).
- **Header Parsing**: `X-Forwarded-For` is trusted only from a configured number of proxy hops (`TRUSTED_PROXY_HOPS`, default `1` in production).
- **Anti-Spoofing**: Attackers attempting to prepend arbitrary IP addresses in `X-Forwarded-For` are thwarted because client IP extraction indexes from the right based on trusted proxy count.
- **Rate Limiters**: All login, registration, and user-level rate limiters operate on this verified client IP.

---

## 4. HTTP Security Headers & Body Limit
The backend injects standard security headers via `SecurityHeadersMiddleware`:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY` (prevents clickjacking)
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: geolocation=(self)` (allows browser GPS exclusively to the application origin)
- `Strict-Transport-Security: max-age=31536000; includeSubDomains` (enforced when `ENV=production`)

**Payload Size Protection**:
- `RequestBodyLimitMiddleware` inspects incoming `Content-Length`.
- Any request with a payload exceeding 1 MB (`1,048,576` bytes) is rejected immediately with HTTP `413 Payload Too Large` to safeguard memory.

---

## 5. Content-Security-Policy (CSP)
A Content-Security-Policy is enforced via the Render static site hosting configuration (`render.yaml`):

```http
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://*.tile.openstreetmap.org https://tile.openstreetmap.org; connect-src 'self' https: wss:; font-src 'self' data:;
```

### Directive Breakdown:
- `default-src 'self'`: Restricts loading resources to the same origin by default.
- `script-src 'self'`: Disallows inline scripts and untrusted third-party scripts.
- `style-src 'self' 'unsafe-inline'`: Permits application stylesheets and Leaflet component styles.
- `img-src 'self' data: https://*.tile.openstreetmap.org https://tile.openstreetmap.org`: Permits map tiles from OpenStreetMap tile servers and inline base64 marker icons.
- `connect-src 'self' https: wss:`: Authorizes HTTPS REST API calls and secure WebSocket (`wss://`) connections.
- `font-src 'self' data:`: Permits modern web typography.

---

## 6. Authentication Hardening
- **Password Strength**: Minimum 10 characters in production; screened against common dictionary passwords (`COMMON_PASSWORDS`).
- **Constant-Time Verification**: Prevents user enumeration by executing a constant-time dummy password hash check even when an email does not exist in the database.
- **Rate Limiting**:
  - Login: 5 failed attempts per 15 minutes per email, 20 attempts per hour per IP. Returns HTTP 429 with `Retry-After`.
  - Registration: 10 registrations per hour per IP.
- **JWT Lifespan & Revocation**:
  - Expiry: 60 minutes (`ACCESS_TOKEN_EXPIRE_MINUTES`).
  - Claims: Standard `sub`, `role`, `iat`, `exp`, and a unique UUID `jti` (JWT ID).
  - Active Check: `is_active` status of the user is checked on every authenticated request.
  - Revocation & Logout (`POST /api/auth/logout`): Revokes the token's `jti` in an in-memory denylist.
  - *Note on Scaling*: The token denylist is stored in process memory. On restart it clears; for multi-instance clusters, a Redis key-value store can be swapped in transparently.

---

## 7. WebSocket Hardening
- **Origin Validation**: WebSocket handshakes check the `Origin` header against `ALLOWED_ORIGINS` in production.
- **Payload Size**: Incoming frame buffer is limited to 16 KB.
- **Message Rate Limiting**: Max 30 messages per 5 seconds per connection; exceeding limits closes the socket with code `4429`.
- **Idle Timeout**: Inactive connections are timed out after 60 seconds of silence; clients maintain connection via periodic `ping`/`pong`.
- **Fault-Tolerant Parsing**: Invalid JSON or unrecognized message types return structured error messages and never crash the server process.

---

## 8. Sensitive Data Redaction & Logging
- **Logging Filter**: `SensitiveDataRedactingFilter` scans every log record before output:
  - Redacts passwords (`password="[REDACTED]"`)
  - Redacts Bearer tokens (`Bearer [REDACTED]`) and standalone JWTs (`[REDACTED_JWT]`)
  - Redacts database connection strings containing credentials (`postgresql+asyncpg://user:[REDACTED]@host/db`)
  - Redacts API keys (`ORS_API_KEY=[REDACTED]`)
- **Global 500 Handler**: Unhandled exceptions return generic responses (`{"error": "Internal server error", "request_id": "<uuid>"}`) with zero stack traces or SQL strings exposed to the client.
- **CSV Formula Injection**: All exported CSV files escape cells starting with `=`, `+`, `-`, or `@` with a leading apostrophe (`'`).

---

## 9. Client Bundle Secret Scan
The repository includes `scripts/check_bundle_secrets.mjs` which runs automatically post-build in CI:
- Recursively inspects the frontend `dist/` directory.
- Flags any occurrence of JWT patterns (`eyJ...`), Neon credentials (`npg_...`), database URLs (`postgresql://`), or `ORS_API_KEY` identifiers.
- Fails the build pipeline if any sensitive string is found.

---

## 10. Dependency Audits
- **Python**: Checked using `pip-audit` for CVEs and `bandit` for static AST security linting.
- **Frontend**: Checked using `npm audit`.
- **Dependabot**: Automated weekly updates configured via `.github/dependabot.yml`.
