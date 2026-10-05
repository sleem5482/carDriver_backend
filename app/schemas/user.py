"""
User Pydantic schemas — Create, Update, Response.
"""

import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr, field_validator

from app.models.user import UserRole, UserStatus


# ── Request Schemas ───────────────────────────────────────

class UserCreate(BaseModel):
    full_name: str
    mobile_number: str
    email: EmailStr | None = None
    password: str | None = None
    role: UserRole = UserRole.DRIVER
    status: UserStatus = UserStatus.ACTIVE
    notes: str | None = None
    vehicle_id: uuid.UUID | None = None  # optional assignment on create

    @field_validator("email", mode="before")
    @classmethod
    def empty_email_to_none(cls, v):
        if isinstance(v, str) and v.strip() == "":
            return None
        return v


class UserUpdate(BaseModel):
    full_name: str | None = None
    mobile_number: str | None = None
    email: EmailStr | None = None
    password: str | None = None
    role: UserRole | None = None
    status: UserStatus | None = None
    notes: str | None = None
    vehicle_id: uuid.UUID | None = None  # re-assign vehicle

    @field_validator("email", mode="before")
    @classmethod
    def empty_email_to_none(cls, v):
        if isinstance(v, str) and v.strip() == "":
            return None
        return v


# ── Response Schemas ──────────────────────────────────────

class VehicleBrief(BaseModel):
    """Minimal vehicle info embedded in user responses."""
    id: uuid.UUID
    plate_number: str
    make: str
    model: str
    status: str

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    mobile_number: str
    email: str | None
    role: UserRole
    status: UserStatus
    notes: str | None
    generated_code: str | None = None
    created_at: datetime
    updated_at: datetime
    assigned_vehicle: VehicleBrief | None = None
    available_vehicles: list[VehicleBrief] = []

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    mobile_number: str
    email: str | None
    role: UserRole
    status: UserStatus
    created_at: datetime

    model_config = {"from_attributes": True}
