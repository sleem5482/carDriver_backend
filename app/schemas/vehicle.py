"""
Vehicle Pydantic schemas.
"""

import uuid
from datetime import datetime
from pydantic import BaseModel, Field

from app.models.vehicle import VehicleStatus


class VehicleCreate(BaseModel):
    vehicle_type: str
    make: str
    model: str
    plate_number: str
    category: str | None = None
    monthly_km: float | None = Field(None, description="Monthly kilometer allowance (e.g. 3000)")
    status: VehicleStatus = VehicleStatus.AVAILABLE


class VehicleUpdate(BaseModel):
    vehicle_type: str | None = None
    make: str | None = None
    model: str | None = None
    plate_number: str | None = None
    category: str | None = None
    monthly_km: float | None = None
    status: VehicleStatus | None = None


class VehicleAvailabilityUpdate(BaseModel):
    """Schema for PATCH /vehicles/{id}/availability — simple on/off toggle."""
    is_available: bool  # True = AVAILABLE, False = NOT AVAILABLE (cannot be changed if ASSIGNED)


class VehicleResponse(BaseModel):
    id: uuid.UUID
    vehicle_type: str
    make: str
    model: str
    plate_number: str
    category: str | None
    monthly_km: float | None
    status: VehicleStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── KM Usage Schemas ──────────────────────────────────────

class DriverKmContribution(BaseModel):
    """How much one driver contributed to this vehicle's total km."""
    driver_id: uuid.UUID
    driver_name: str
    km_used: float


class VehicleKmUsageResponse(BaseModel):
    """
    Aggregated km-usage report for a single vehicle.

    - total_km_used: sum of all completed trip km for this vehicle (all time)
    - monthly_km_limit: the configured monthly allowance (null if not set)
    - overtime_km: max(0, total_km_used - monthly_km_limit) — null if no limit set
    - is_over_limit: True when overtime_km > 0
    - drivers: per-driver breakdown
    """
    vehicle_id: uuid.UUID
    plate_number: str
    make: str
    model: str
    monthly_km_limit: float | None
    total_km_used: float
    overtime_km: float | None
    is_over_limit: bool
    drivers: list[DriverKmContribution]
