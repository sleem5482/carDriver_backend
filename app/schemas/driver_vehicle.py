"""
Driver–Vehicle Assignment schemas.
"""

import uuid
from datetime import datetime
from pydantic import BaseModel


class AssignmentCreate(BaseModel):
    driver_id: uuid.UUID
    vehicle_id: uuid.UUID


class AssignmentResponse(BaseModel):
    id: uuid.UUID
    driver_id: uuid.UUID
    vehicle_id: uuid.UUID
    is_active: bool
    assigned_at: datetime
    unassigned_at: datetime | None

    model_config = {"from_attributes": True}
