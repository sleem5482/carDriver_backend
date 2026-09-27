"""
Audit service — write audit log entries.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def log_action(
    db: Session,
    *,
    user_id: str | None,
    action: str,
    old_value: dict | None = None,
    new_value: dict | None = None,
    reason: str | None = None,
) -> AuditLog:
    """
    Create an audit log entry.
    server_datetime is always UTC server time — never trust client time.
    """
    entry = AuditLog(
        user_id=user_id,
        action=action,
        old_value=old_value,
        new_value=new_value,
        reason=reason,
        server_datetime=datetime.now(timezone.utc),
    )
    db.add(entry)
    db.flush()  # so caller can read entry.id if needed
    return entry
