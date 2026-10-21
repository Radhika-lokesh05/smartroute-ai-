import asyncio
import logging
import pytest
from httpx import AsyncClient
from starlette.requests import Request
from starlette.datastructures import Headers

from app.core.config import Settings
from app.core.network import get_client_ip
from app.core.logging import redact_sensitive_text, SensitiveDataRedactingFilter
from app.core.security import (
    validate_password_strength,
    create_access_token,
    revoke_token,
    is_token_revoked,
    check_login_rate_limits,
    record_login_failure,
    record_login_success,
)


def test_production_security_validation_refuses_insecure_configs():
    """Verify validate_production_security raises RuntimeError for insecure configs in production."""
    # 1. Short JWT_SECRET
    s1 = Settings(
        ENV="production",
        JWT_SECRET="short_secret",
        DATABASE_URL="postgresql+asyncpg://user:pass@ep-valid.us-east-2.aws.neon.tech/neondb?ssl=require",
        ALLOWED_ORIGINS=["https://app.smartroute.ai"],
    )
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        s1.validate_production_security()

    # 2. Insecure placeholder JWT_SECRET
    s2 = Settings(
        ENV="production",
        JWT_SECRET="your_jwt_secret_key_minimum_32_characters_long",
        DATABASE_URL="postgresql+asyncpg://user:pass@ep-valid.us-east-2.aws.neon.tech/neondb?ssl=require",
        ALLOWED_ORIGINS=["https://app.smartroute.ai"],
    )
    with pytest.raises(RuntimeError, match="placeholder"):
        s2.validate_production_security()

    # 3. Wildcard ALLOWED_ORIGINS
    s3 = Settings(
        ENV="production",
        JWT_SECRET="super_strong_production_jwt_secret_at_least_32_chars!",
        DATABASE_URL="postgresql+asyncpg://user:pass@ep-valid.us-east-2.aws.neon.tech/neondb?ssl=require",
        ALLOWED_ORIGINS=["*"],
    )
    with pytest.raises(RuntimeError, match="Wildcard"):
        s3.validate_production_security()

    # 4. External non-SSL HTTP origin
    s4 = Settings(
        ENV="production",
        JWT_SECRET="super_strong_production_jwt_secret_at_least_32_chars!",
        DATABASE_URL="postgresql+asyncpg://user:pass@ep-valid.us-east-2.aws.neon.tech/neondb?ssl=require",
        ALLOWED_ORIGINS=["http://external-website.com"],
    )
    with pytest.raises(RuntimeError, match="Non-HTTPS origin forbidden"):
        s4.validate_production_security()

    # 5. Missing or placeholder DATABASE_URL
    s5 = Settings(
        ENV="production",
        JWT_SECRET="super_strong_production_jwt_secret_at_least_32_chars!",
        DATABASE_URL="postgresql+asyncpg://user:pass@ep-placeholder.aws.neon.tech/neondb?ssl=require",
        ALLOWED_ORIGINS=["https://app.smartroute.ai"],
    )
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        s5.validate_production_security()

    # 6. Valid production config passes cleanly
    s_valid = Settings(
        ENV="production",
        JWT_SECRET="super_strong_production_jwt_secret_at_least_32_chars!",
        DATABASE_URL="postgresql+asyncpg://prod_user:prod_pass@ep-prod-cluster.aws.neon.tech/neondb?ssl=require",
        ALLOWED_ORIGINS=["https://app.smartroute.ai", "http://localhost:5173"],
    )
    s_valid.validate_production_security()  # Should not raise


def test_password_strength_validator():
    """Verify password strength validation in production mode."""
    # Too short (< 10 in production)
    is_valid, msg = validate_password_strength("Short1!", is_production=True)
    assert not is_valid
    assert "at least 10 characters" in msg

    # Common password rejected
    is_valid, msg = validate_password_strength("password123", is_production=True)
    assert not is_valid
    assert "too common" in msg

    # Good password accepted
    is_valid, msg = validate_password_strength("SecureP@ssw0rd2026!Strong", is_production=True)
    assert is_valid


def test_sensitive_data_redaction():
    """Verify passwords, tokens, API keys, and database URLs are redacted."""
    raw_log = 'User logged in with password="superSecretPassword123" and token Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.doNotLeakThis'
    redacted = redact_sensitive_text(raw_log)
    assert "superSecretPassword123" not in redacted
    assert "[REDACTED]" in redacted

    db_url_log = "Connected to postgresql+asyncpg://neon_owner:Npg_secretPassword@ep-pool.aws.neon.tech/neondb?ssl=require"
    redacted_db = redact_sensitive_text(db_url_log)
    assert "Npg_secretPassword" not in redacted_db
    assert "[REDACTED]" in redacted_db

    # Test logging filter
    filter_obj = SensitiveDataRedactingFilter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="DATABASE_URL is postgresql+asyncpg://user:pass123@host/db",
        args=(),
        exc_info=None,
    )
    filter_obj.filter(record)
    assert "pass123" not in record.msg


def test_client_ip_reverse_proxy_anti_spoofing():
    """Verify TRUSTED_PROXY_HOPS correctly prevents client IP spoofing."""
    scope = {
        "type": "http",
        "client": ("10.0.0.1", 12345),
        "headers": [
            (b"x-forwarded-for", b"203.0.113.195, 198.51.100.10"),
        ],
    }
    req = Request(scope)

    # With TRUSTED_PROXY_HOPS = 1, real client is 198.51.100.10 (one hop before proxy)
    ip_hop1 = get_client_ip(req, trusted_proxy_hops=1)
    assert ip_hop1 == "198.51.100.10"

    # With TRUSTED_PROXY_HOPS = 2, real client is 203.0.113.195
    ip_hop2 = get_client_ip(req, trusted_proxy_hops=2)
    assert ip_hop2 == "203.0.113.195"

    # Client cannot prepend fake IPs to fool a single-hop reverse proxy:
    # If attacker sends X-Forwarded-For: "1.1.1.1", Render appends real client IP "203.0.113.195"
    # Result: "1.1.1.1, 203.0.113.195". With TRUSTED_PROXY_HOPS=1, hop from right is "203.0.113.195".
    scope_spoof = {
        "type": "http",
        "client": ("10.0.0.1", 12345),
        "headers": [
            (b"x-forwarded-for", b"1.1.1.1, 203.0.113.195"),
        ],
    }
    req_spoof = Request(scope_spoof)
    assert get_client_ip(req_spoof, trusted_proxy_hops=1) == "203.0.113.195"


def test_token_jti_and_in_memory_denylist():
    """Verify token jti issuance and logout denylist."""
    from app.core.security import decode_access_token
    token = create_access_token(user_id="user-123", role="civilian")
    payload = decode_access_token(token)
    jti = payload.get("jti")
    assert jti is not None
    assert not is_token_revoked(jti)

    revoke_token(jti)
    assert is_token_revoked(jti)


@pytest.mark.asyncio
async def test_security_headers_and_payload_limit(client: AsyncClient):
    """Verify security headers middleware and 1 MB payload rejection."""
    # Test security headers on GET /health
    res = await client.get("/health")
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "DENY"
    assert "strict-origin-when-cross-origin" in res.headers.get("Referrer-Policy", "")
    assert "geolocation=(self)" in res.headers.get("Permissions-Policy", "")
    assert "X-Request-ID" in res.headers

    # Test payload size limit > 1 MB
    huge_data = "a" * (1024 * 1024 + 50)  # > 1 MB
    res_large = await client.post(
        "/api/auth/login",
        content=huge_data,
        headers={"Content-Length": str(len(huge_data)), "Content-Type": "application/json"},
    )
    assert res_large.status_code == 413
    assert res_large.json().get("error") == "Payload Too Large"
