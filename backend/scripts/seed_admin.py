import asyncio
import os
import sys
from pathlib import Path

# Add backend directory to sys.path so app modules are resolvable
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select
from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.core.security import get_password_hash
from app.models.user import User, UserRole


async def seed_admin() -> None:
    """
    Seed initial administrator user if one does not already exist.
    Reads credentials from ADMIN_EMAIL and ADMIN_PASSWORD environment variables or .env.
    """
    admin_email = os.getenv("ADMIN_EMAIL") or settings.ADMIN_EMAIL
    admin_password = os.getenv("ADMIN_PASSWORD") or settings.ADMIN_PASSWORD

    if not admin_email or not admin_password:
        print("[seed_admin] ERROR: ADMIN_EMAIL and ADMIN_PASSWORD must be configured in environment or .env.")
        sys.exit(1)

    normalized_email = admin_email.lower().strip()

    async with AsyncSessionLocal() as session:
        # Check if admin user already exists
        stmt = select(User).where(User.email == normalized_email)
        result = await session.execute(stmt)
        existing_admin = result.scalar_one_or_none()

        if existing_admin is not None:
            print(f"[seed_admin] Admin user '{normalized_email}' already exists. No action taken.")
            return

        print(f"[seed_admin] Creating admin user: {normalized_email}...")
        admin_user = User(
            name="System Administrator",
            email=normalized_email,
            password_hash=get_password_hash(admin_password),
            role=UserRole.admin,
            is_active=True,
        )
        session.add(admin_user)
        await session.commit()
        print(f"[seed_admin] Admin user '{normalized_email}' successfully created with role=admin.")


async def _async_main() -> None:
    try:
        await seed_admin()
    finally:
        await engine.dispose()
        # Brief pause to allow Windows asyncpg SSL transport disconnect callbacks to cleanly flush
        await asyncio.sleep(0.1)


def main() -> None:
    # Use SelectorEventLoop on Windows to avoid ProactorEventLoop SSL cleanup crash on loop close
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
