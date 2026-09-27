"""
Audit Log schemas.
"""

import uuid
from datetime import datetime
from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    action: str
    old_value: dict | None = None
    new_value: dict | None = None
    reason: str | None = None
    server_datetime: datetime

    model_config = {"from_attributes": True}
