"""
Cleanup script for SmartRoute AI simulated data.
Safely removes all incidents, dispatches, and associated records flagged as is_simulated.

Default behavior is a DRY RUN. Pass --yes to confirm deletion.

Usage:
    python scripts/cleanup_simulated.py --admin-email admin@smartroute.ai --admin-password <PW> [--yes]
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path

# Add backend directory to sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = WORKSPACE_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Add virtual environment site-packages if available
venv_sites = [
    BACKEND_DIR / "venv" / "Lib" / "site-packages",
    BACKEND_DIR / ".venv" / "Lib" / "site-packages",
    WORKSPACE_ROOT / "venv" / "Lib" / "site-packages",
]
for p in venv_sites:
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

from sqlalchemy import delete, select, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings
from app.models.incident import Incident, IncidentVote
from app.models.dispatch import Dispatch
from app.models.ambulance import Ambulance, AmbulanceStatus
from app.models.user import User


async def run_cleanup(dry_run: bool = True) -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Count simulated incidents
        inc_count = (await session.execute(
            select(func.count(Incident.id)).where(Incident.is_simulated.is_(True))
        )).scalar_one()

        # Count simulated dispatches
        disp_count = (await session.execute(
            select(func.count(Dispatch.id)).where(Dispatch.is_simulated.is_(True))
        )).scalar_one()

        # Count simulated users
        sim_users_stmt = select(func.count(User.id)).where(User.email.like("sim_%@smartroute.ai"))
        user_count = (await session.execute(sim_users_stmt)).scalar_one()

        # Count simulated ambulances
        sim_amb_stmt = select(func.count(Ambulance.id)).where(Ambulance.plate_number.like("SIM-AMB-%"))
        amb_count = (await session.execute(sim_amb_stmt)).scalar_one()

        print(f"\n{'[DRY RUN]' if dry_run else '[EXECUTING CLEANUP]'}")
        print(f"  Simulated incidents:  {inc_count}")
        print(f"  Simulated dispatches: {disp_count}")
        print(f"  Simulated ambulances: {amb_count}")
        print(f"  Simulated users:      {user_count}")

        if dry_run:
            print("\nDry run complete. No records were modified or deleted.")
            print("To permanently remove simulated data, re-run with: --yes\n")
            await engine.dispose()
            return

        # Execution: delete dispatches first
        await session.execute(delete(Dispatch).where(Dispatch.is_simulated.is_(True)))

        # Delete votes on simulated incidents
        sim_inc_ids_res = await session.execute(
            select(Incident.id).where(Incident.is_simulated.is_(True))
        )
        sim_inc_ids = list(sim_inc_ids_res.scalars().all())
        if sim_inc_ids:
            await session.execute(
                delete(IncidentVote).where(IncidentVote.incident_id.in_(sim_inc_ids))
            )

        # Delete simulated incidents
        await session.execute(delete(Incident).where(Incident.is_simulated.is_(True)))

        # Reset any remaining ambulances to available if they were busy
        ambs_res = await session.execute(
            select(Ambulance).where(Ambulance.plate_number.like("SIM-AMB-%"))
        )
        for amb in ambs_res.scalars().all():
            amb.status = AmbulanceStatus.available

        await session.commit()
        print("\nCleanup completed successfully! All simulated incidents and dispatches removed.\n")

    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="SmartRoute AI Simulated Data Cleanup Tool")
    parser.add_argument("--yes", action="store_true", help="Confirm deletion (default is dry-run)")
    args = parser.parse_args()

    asyncio.run(run_cleanup(dry_run=not args.yes))


if __name__ == "__main__":
    main()
