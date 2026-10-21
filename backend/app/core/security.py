import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
import bcrypt
from fastapi import HTTPException, status
from jose import jwt
from app.core.config import settings

ALGORITHM = "HS256"

# Common weak passwords checked in production
COMMON_PASSWORDS = {
    "password123",
    "password1234",
    "1234567890",
    "123456789",
    "12345678",
    "qwerty1234",
    "admin12345",
    "welcome123",
    "letmein123",
    "smartroute123",
    "iloveyou123",
    "pass123456",
}

# Pre-computed dummy hash to prevent timing attacks when an email does not exist
DUMMY_PASSWORD_HASH = "$2b$12$e8Y5t1hR0mH/8Z0pL7rGue7Z8jC.2qM0vJ9s8qQ3wY4t1hR0mH/8Z"

# In-memory token denylist for revoked JWTs (jti -> expiration_timestamp)
# NOTE: Resets upon server restart. For distributed/multi-instance architectures,
# an external key-value store (such as Redis) or persistent database table can replace this.
TOKEN_DENYLIST: Dict[str, float] = {}

# In-memory authentication rate limit trackers
# IP -> list of timestamps
_LOGIN_IP_ATTEMPTS: Dict[str, List[float]] = {}
# Email -> list of failed attempt timestamps
_LOGIN_EMAIL_FAILURES: Dict[str, List[float]] = {}
# IP -> list of register timestamps
_REGISTER_IP_ATTEMPTS: Dict[str, List[float]] = {}


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt-hashed password."""
    try:
        password_bytes = plain_password.encode("utf-8")
        hash_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hash_bytes)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Generate a bcrypt password hash."""
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def validate_password_strength(
    password: str,
    is_production: Optional[bool] = None,
    raise_exception: bool = False,
) -> Tuple[bool, str]:
    """
    Validate password requirements.
    In production: minimum 10 characters, and not in common passwords list.
    """
    prod = is_production if is_production is not None else (settings.ENV.lower() == "production")
    if prod:
        if len(password) < 10:
            msg = "Password must be at least 10 characters long in production."
            if raise_exception:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
            return False, msg
        if password.lower() in COMMON_PASSWORDS:
            msg = "Password is too common and easily guessed. Please choose a stronger password."
            if raise_exception:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
            return False, msg
    else:
        if len(password) < 8:
            msg = "Password must be at least 8 characters long."
            if raise_exception:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
            return False, msg
    return True, ""


def create_access_token(
    subject: Optional[str] = None,
    role: str = "civilian",
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
) -> str:
    """Generate a signed JWT access token with role, subject, iat, exp, and jti."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    sub = str(user_id if user_id is not None else subject)
    to_encode: Dict[str, Any] = {
        "sub": sub,
        "role": str(role),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": str(uuid.uuid4()),
    }
    if extra_claims:
        to_encode.update(extra_claims)

    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a signed JWT access token."""
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])


def revoke_token(jti: str, exp_timestamp: Optional[float] = None) -> None:
    """Add a token jti to the in-memory denylist."""
    now = time.time()
    if exp_timestamp is None:
        exp_timestamp = now + (settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    # Prune expired tokens to avoid unbounded memory growth
    expired = [k for k, v in TOKEN_DENYLIST.items() if v <= now]
    for k in expired:
        TOKEN_DENYLIST.pop(k, None)

    TOKEN_DENYLIST[jti] = exp_timestamp


def is_token_revoked(jti: Optional[str]) -> bool:
    """Check whether a token jti has been revoked via logout."""
    if not jti:
        return False
    exp = TOKEN_DENYLIST.get(jti)
    if exp is None:
        return False
    if time.time() > exp:
        TOKEN_DENYLIST.pop(jti, None)
        return False
    return True


def check_login_rate_limits(ip: str, email: str) -> None:
    """
    Check rate limits for login attempts:
    - Max 20 attempts per hour per IP.
    - Max 5 failed attempts per 15 minutes per email.
    """
    now = time.time()

    # 1. Check IP rate limit (20 / hour)
    ip_attempts = _LOGIN_IP_ATTEMPTS.get(ip, [])
    # Keep timestamps within the last 3600 seconds
    ip_attempts = [t for t in ip_attempts if now - t < 3600]
    _LOGIN_IP_ATTEMPTS[ip] = ip_attempts
    if len(ip_attempts) >= 20:
        oldest = ip_attempts[0]
        retry_after = max(1, int(3600 - (now - oldest)))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts from this IP address. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    # 2. Check Email failed attempts (5 / 15 minutes)
    norm_email = email.lower().strip()
    email_failures = _LOGIN_EMAIL_FAILURES.get(norm_email, [])
    email_failures = [t for t in email_failures if now - t < 900]
    _LOGIN_EMAIL_FAILURES[norm_email] = email_failures
    if len(email_failures) >= 5:
        oldest = email_failures[0]
        retry_after = max(1, int(900 - (now - oldest)))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts for this account. Please wait before retrying.",
            headers={"Retry-After": str(retry_after)},
        )


def record_login_attempt(ip: str) -> None:
    """Record an IP login request."""
    now = time.time()
    attempts = _LOGIN_IP_ATTEMPTS.setdefault(ip, [])
    attempts.append(now)


def record_login_failure(email: str) -> None:
    """Record a failed login attempt for an email."""
    now = time.time()
    failures = _LOGIN_EMAIL_FAILURES.setdefault(email.lower().strip(), [])
    failures.append(now)


def record_login_success(email: str) -> None:
    """Clear failed login records for an email upon successful login."""
    _LOGIN_EMAIL_FAILURES.pop(email.lower().strip(), None)


def check_register_rate_limit(ip: str) -> None:
    """Check rate limit for registrations (max 20 per hour per IP)."""
    now = time.time()
    attempts = _REGISTER_IP_ATTEMPTS.get(ip, [])
    attempts = [t for t in attempts if now - t < 3600]
    _REGISTER_IP_ATTEMPTS[ip] = attempts
    if len(attempts) >= 20:
        oldest = attempts[0]
        retry_after = max(1, int(3600 - (now - oldest)))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many registrations from this IP address. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )
    attempts.append(now)
