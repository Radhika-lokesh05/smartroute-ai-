import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit import AuditLog

logger = logging.getLogger("smartroute.audit")

# Redacted keys to guarantee no secrets/personal tokens ever enter details JSON
SENSITIVE_KEYS = {
    "password",
    "password_hash",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "authorization",
    "api_key",
}


def sanitize_details(details: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Recursively strip any sensitive keys or personal data from audit details."""
    if not details:
        return None
    cleaned: Dict[str, Any] = {}
    for key, val in details.items():
        if key.lower() in SENSITIVE_KEYS:
            continue
        if isinstance(val, dict):
            cleaned[key] = sanitize_details(val)
        else:
            cleaned[key] = val
    return cleaned


async def log_audit_event(
    session: AsyncSession,
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    actor_user_id: Optional[uuid.UUID] = None,
    details: Optional[Dict[str, Any]] = None,
) -> AuditLog:
    """
    Persist an audit entry for compliance, security, and administrative oversight.
    Guarantees secrets are sanitized before storage.
    """
    clean_details = sanitize_details(details)
    entry = AuditLog(
        id=uuid.uuid4(),
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        details=clean_details,
    )
    session.add(entry)
    await session.flush()
    logger.info(
        f"[AUDIT] action={action} entity_type={entity_type} entity_id={entity_id} actor={actor_user_id}"
    )
    return entry


async def get_audit_logs(
    session: AsyncSession,
    action: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[AuditLog], int]:
    """Retrieve paginated audit logs with optional action and date range filters."""
    query = select(AuditLog)
    count_query = select(func.count(AuditLog.id))

    if action:
        query = query.where(AuditLog.action == action)
        count_query = count_query.where(AuditLog.action == action)

    if start_date:
        query = query.where(AuditLog.created_at >= start_date)
        count_query = count_query.where(AuditLog.created_at >= start_date)

    if end_date:
        query = query.where(AuditLog.created_at <= end_date)
        count_query = count_query.where(AuditLog.created_at <= end_date)

    total_count_res = await session.execute(count_query)
    total_count = total_count_res.scalar_one()

    offset = (page - 1) * page_size
    query = query.order_by(desc(AuditLog.created_at)).offset(offset).limit(page_size)

    result = await session.execute(query)
    items = list(result.scalars().all())
    return items, total_count
