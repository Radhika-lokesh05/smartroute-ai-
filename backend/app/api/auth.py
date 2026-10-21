from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.network import get_client_ip
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    check_login_rate_limits,
    check_register_rate_limit,
    create_access_token,
    get_password_hash,
    record_login_attempt,
    record_login_failure,
    record_login_success,
    revoke_token,
    validate_password_strength,
    verify_password,
)
from app.api.deps import get_current_token_payload, get_current_user
from app.models.user import User, UserRole
from app.schemas.user import TokenResponse, UserLogin, UserRegister, UserResponse

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_in: UserRegister,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Public registration endpoint.
    - Rate limited per client IP (20 per hour).
    - In production, enforces minimum 10-char password and common password dictionary checks.
    - ALWAYS creates a user with role=civilian.
    """
    client_ip = get_client_ip(request)
    check_register_rate_limit(client_ip)

    # Validate password requirements
    validate_password_strength(user_in.password, raise_exception=True)

    normalized_email = user_in.email.lower().strip()

    # Check for duplicate email
    stmt = select(User).where(User.email == normalized_email)
    existing_user = (await db.execute(stmt)).scalar_one_or_none()
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Always enforce role=civilian
    new_user = User(
        name=user_in.name.strip(),
        email=normalized_email,
        password_hash=get_password_hash(user_in.password),
        role=UserRole.civilian,
        is_active=True,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return UserResponse.model_validate(new_user)


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    User authentication endpoint returning JWT bearer token.
    - Enforces rate limiting per IP and per email.
    - Constant-time password check prevents user enumeration timing attacks.
    - Checks account active status.
    """
    client_ip = get_client_ip(request)
    normalized_email = credentials.email.lower().strip()

    # Enforce rate limits before processing
    check_login_rate_limits(client_ip, normalized_email)
    record_login_attempt(client_ip)

    stmt = select(User).where(User.email == normalized_email)
    user = (await db.execute(stmt)).scalar_one_or_none()

    if user is None:
        # Constant-time dummy check to prevent timing attack enumeration
        verify_password(credentials.password, DUMMY_PASSWORD_HASH)
        record_login_failure(normalized_email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(credentials.password, user.password_hash):
        record_login_failure(normalized_email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        record_login_failure(normalized_email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Reset failed login records on success
    record_login_success(normalized_email)

    token = create_access_token(
        subject=str(user.id),
        role=user.role.value,
        extra_claims={"email": user.email},
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.post("/logout")
async def logout(
    payload: Dict[str, Any] = Depends(get_current_token_payload),
) -> dict:
    """
    Revoke current JWT access token via in-memory denylist.
    NOTE: In-memory denylist resets upon server restart.
    For horizontal multi-instance scaling, Redis or an external key-value store can replace this.
    """
    jti = payload.get("jti")
    exp = float(payload.get("exp", 0))
    if jti:
        revoke_token(jti, exp)

    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """
    Retrieve profile details of currently authenticated user.
    """
    return UserResponse.model_validate(current_user)
