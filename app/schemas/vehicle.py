"""
Vehicle Pydantic schemas.
"""

import uuid
from datetime import datetime, date
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


# ── Vehicle Report Schemas ────────────────────────────────

class TripBrief(BaseModel):
    """Summary of one trip in the vehicle report."""
    trip_id: uuid.UUID
    driver_name: str
    start_date: date
    start_location: str
    end_location: str | None
    start_odometer: float
    end_odometer: float | None
    km_used: float | None
    working_hours_formatted: str | None
    status: str
    verification_status: str


class DriverKmSummary(BaseModel):
    """Per-driver km contribution for a vehicle."""
    driver_id: uuid.UUID
    driver_name: str
    total_km: float
    trip_count: int


class AssignedDriverBrief(BaseModel):
    """Currently assigned driver info."""
    driver_id: uuid.UUID
    driver_name: str
    mobile_number: str
    assigned_at: datetime


class VehicleReportResponse(BaseModel):
    """
    Full vehicle report returned by GET /admin/vehicles/{id}/report.

    Includes:
    - Vehicle details (monthly_km limit)
    - Currently assigned driver (if any)
    - km-usage totals with overtime calculation
    - Per-driver km breakdown
    - Individual trip list (filtered by date range if provided)
    """
    # ── Vehicle info ──────────────────────────────────────
    vehicle_id: uuid.UUID
    plate_number: str
    vehicle_type: str
    make: str
    model: str
    category: str | None
    status: VehicleStatus
    monthly_km_limit: float | None

    # ── Current assignment ─────────────────────────────────
    assigned_driver: AssignedDriverBrief | None

    # ── Date filter applied ────────────────────────────────
    date_from: date | None
    date_to: date | None

    # ── KM summary ────────────────────────────────────────
    total_km_used: float
    overtime_km: float | None       # null if no monthly_km_limit set
    is_over_limit: bool

    # ── Driver breakdown ──────────────────────────────────
    drivers: list[DriverKmSummary]

    # ── Trip list ─────────────────────────────────────────
    trips: list[TripBrief]
