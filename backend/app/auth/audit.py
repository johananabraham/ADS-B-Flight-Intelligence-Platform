"""Small, explicit helpers for security audit records."""

from typing import Any

from sqlalchemy.orm import Session

from ..models.user import AuditEvent


_ALLOWED_DETAIL_TYPES = (str, int, float, bool, type(None))


def record_audit_event(
    db: Session,
    *,
    event_type: str,
    success: bool,
    actor_user_id: int | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditEvent:
    """Add a bounded audit record to the caller's current transaction."""
    safe_details = {
        str(key)[:64]: value
        for key, value in (details or {}).items()
        if isinstance(value, _ALLOWED_DETAIL_TYPES)
    }
    event = AuditEvent(
        event_type=event_type[:64],
        success=success,
        actor_user_id=actor_user_id,
        target_type=target_type[:64] if target_type else None,
        target_id=target_id[:128] if target_id else None,
        details=safe_details,
    )
    db.add(event)
    return event
