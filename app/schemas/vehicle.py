"""
Vehicle Pydantic schemas.
"""

import uuid
from datetime import datetime
from pydantic import BaseModel

from app.models.vehicle import VehicleStatus


class VehicleCreate(BaseModel):
    vehicle_type: str
    make: str
    model: str
    plate_number: str
    category: str | None = None
    status: VehicleStatus = VehicleStatus.AVAILABLE


class VehicleUpdate(BaseModel):
    vehicle_type: str | None = None
    make: str | None = None
    model: str | None = None
    plate_number: str | None = None
    category: str | None = None
    status: VehicleStatus | None = None


class VehicleResponse(BaseModel):
    id: uuid.UUID
    vehicle_type: str
    make: str
    model: str
    plate_number: str
    category: str | None
    status: VehicleStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
