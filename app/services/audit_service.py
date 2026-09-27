"""
Audit service — write audit log entries.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


import uuid

def log_action(
    db: Session,
    *,
    user_id: str | uuid.UUID | None,
    action: str,
    old_value: dict | None = None,
    new_value: dict | None = None,
    reason: str | None = None,
) -> AuditLog:
    """
    Create an audit log entry.
    server_datetime is always UTC server time — never trust client time.
    """
    if isinstance(user_id, str):
        try:
            user_id = uuid.UUID(user_id)
        except ValueError:
            pass  # if it's not a valid UUID string, let it pass or handle it? We can just pass it and let DB fail, or set to None. Actually, user_id should always be a valid UUID here.

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
