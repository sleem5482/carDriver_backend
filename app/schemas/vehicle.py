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
    daily_shift_hours: float | None = Field(None, description="Daily shift limit in hours (e.g. 8.0)")
    status: VehicleStatus = VehicleStatus.AVAILABLE


class VehicleUpdate(BaseModel):
    vehicle_type: str | None = None
    make: str | None = None
    model: str | None = None
    plate_number: str | None = None
    category: str | None = None
    monthly_km: float | None = None
    daily_shift_hours: float | None = None
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
    daily_shift_hours: float | None
    status: VehicleStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Vehicle Report Schemas ────────────────────────────────

class TripBrief(BaseModel):
    """Summary of one trip in the vehicle report."""
    trip_id: uuid.UUID
    driver_id: uuid.UUID
    driver_name: str
    start_date: date
    start_location: str
    end_location: str | None
    start_odometer: float
    end_odometer: float | None
    km_used: float | None
    working_hours_formatted: str | None
    overtime_hours: float | None
    status: str
    verification_status: str


class DriverKmSummary(BaseModel):
    """Per-driver km contribution for a vehicle."""
    driver_id: uuid.UUID
    driver_name: str
    total_km: float
    trip_count: int


class AssignmentRecord(BaseModel):
    """One assignment period for a driver on this vehicle."""
    assigned_at: datetime
    unassigned_at: datetime | None
    is_active: bool


class DriverReport(BaseModel):
    """
    Full per-driver breakdown inside the vehicle report.

    Shows every driver who was ever assigned to (or drove) this vehicle,
    together with their assignment history, km totals, and individual trips.
    """
    driver_id: uuid.UUID
    driver_name: str
    mobile_number: str
    # Assignment history for this driver on this vehicle
    assignments: list[AssignmentRecord]
    is_currently_assigned: bool
    # km / trip aggregates (only counts completed trips)
    total_km: float
    trip_count: int
    # All trips (OPEN + COMPLETED) this driver made with this vehicle
    trips: list[TripBrief]


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
    - Per-driver km breakdown (all drivers who ever used the vehicle)
    - Per-driver detail: assignment history + all trips (OPEN & COMPLETED)
    - Flat trip list (all trips, filterable by date range)
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
    daily_shift_hours: float | None       # daily working-hour shift limit

    # ── Current assignment ─────────────────────────────────
    assigned_driver: AssignedDriverBrief | None

    # ── Date filter applied ────────────────────────────────
    date_from: date | None
    date_to: date | None

    # ── KM summary (completed trips only) ─────────────────
    total_km_used: float
    overtime_km: float | None       # null if no monthly_km_limit set
    is_over_limit: bool

    # ── High-level driver km breakdown ────────────────────
    drivers: list[DriverKmSummary]

    # ── Per-driver full detail (assignments + all trips) ───
    driver_reports: list[DriverReport]

    # ── Flat trip list (all trips, date-filtered) ──────────
    trips: list[TripBrief]
