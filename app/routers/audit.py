"""
Admin Audit Logs router — read-only access to audit trail.
"""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_admin
from app.models.user import User
from app.models.audit_log import AuditLog
from app.schemas.audit_log import AuditLogResponse

router = APIRouter(prefix="/admin/audit-logs", tags=["Admin – Audit Logs"])


@router.get("/", response_model=list[AuditLogResponse])
def list_audit_logs(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    action: str | None = Query(None, description="Filter by action type, e.g. LOGIN, CREATE_USER"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Retrieve audit log entries with optional filters."""
    query = db.query(AuditLog)

    if date_from:
        query = query.filter(AuditLog.server_datetime >= date_from)
    if date_to:
        query = query.filter(AuditLog.server_datetime <= date_to)
    if action:
        query = query.filter(AuditLog.action == action)

    return (
        query
        .order_by(AuditLog.server_datetime.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
