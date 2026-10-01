"""
Admin Vehicles router — full CRUD + km-usage reporting.
"""

import uuid
from typing import Optional
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_admin
from app.models.user import User
from app.models.trip import Trip, TripStatus
from app.models.vehicle import Vehicle, VehicleStatus
from app.schemas.vehicle import (
    VehicleCreate, VehicleUpdate, VehicleResponse, VehicleAvailabilityUpdate,
    VehicleKmUsageResponse, DriverKmContribution,
)
from app.services.audit_service import log_action
from app.utils.exceptions import not_found, conflict

router = APIRouter(prefix="/admin/vehicles", tags=["Admin – Vehicles"])


# ── CRUD ──────────────────────────────────────────────────

@router.get("/", response_model=list[VehicleResponse])
def list_vehicles(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """List all vehicles."""
    return db.query(Vehicle).order_by(Vehicle.created_at.desc()).all()


@router.get("/{vehicle_id}", response_model=VehicleResponse)
def get_vehicle(
    vehicle_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Get a single vehicle by ID."""
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise not_found("Vehicle not found.")
    return vehicle


@router.post("/", response_model=VehicleResponse, status_code=201)
def create_vehicle(
    body: VehicleCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Create a new vehicle. Optionally set `monthly_km` as the km allowance."""
    if db.query(Vehicle).filter(Vehicle.plate_number == body.plate_number).first():
        raise conflict("Plate number already exists.")

    vehicle = Vehicle(**body.model_dump())
    db.add(vehicle)

    log_action(
        db,
        user_id=str(admin.id),
        action="CREATE_VEHICLE",
        new_value=body.model_dump(),
    )
    db.commit()
    db.refresh(vehicle)
    return vehicle


@router.put("/{vehicle_id}", response_model=VehicleResponse)
def update_vehicle(
    vehicle_id: uuid.UUID,
    body: VehicleUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Update vehicle details. You can set or change `monthly_km` here."""
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise not_found("Vehicle not found.")

    old_values = {
        "vehicle_type": vehicle.vehicle_type,
        "make": vehicle.make,
        "model": vehicle.model,
        "plate_number": vehicle.plate_number,
        "category": vehicle.category,
        "monthly_km": vehicle.monthly_km,
        "status": vehicle.status.value,
    }

    update_data = body.model_dump(exclude_unset=True)

    # Check plate uniqueness if changing
    if "plate_number" in update_data:
        existing = (
            db.query(Vehicle)
            .filter(Vehicle.plate_number == update_data["plate_number"], Vehicle.id != vehicle_id)
            .first()
        )
        if existing:
            raise conflict("Plate number already exists.")

    for field, value in update_data.items():
        setattr(vehicle, field, value)

    log_action(
        db,
        user_id=str(admin.id),
        action="UPDATE_VEHICLE",
        old_value=old_values,
        new_value=update_data,
    )
    db.commit()
    db.refresh(vehicle)
    return vehicle


@router.patch("/{vehicle_id}/availability", response_model=VehicleResponse)
def update_vehicle_availability(
    vehicle_id: uuid.UUID,
    body: VehicleAvailabilityUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Toggle a vehicle's availability.
    - `is_available: true`  → sets status to AVAILABLE
    - `is_available: false` → sets status to NOT_AVAILABLE
    Cannot change an ASSIGNED vehicle — unassign the driver first.
    """
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise not_found("Vehicle not found.")

    # Block if the vehicle is currently assigned to a driver
    if vehicle.status == VehicleStatus.ASSIGNED:
        raise conflict("Vehicle is currently assigned to a driver. Unassign the driver first.")

    new_status = VehicleStatus.AVAILABLE if body.is_available else VehicleStatus.NOT_AVAILABLE
    old_status = vehicle.status.value
    vehicle.status = new_status

    log_action(
        db,
        user_id=str(admin.id),
        action="UPDATE_VEHICLE_AVAILABILITY",
        old_value={"status": old_status},
        new_value={"status": new_status.value, "is_available": body.is_available},
    )
    db.commit()
    db.refresh(vehicle)
    return vehicle


@router.delete("/{vehicle_id}", status_code=204)
def delete_vehicle(
    vehicle_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Delete a vehicle."""
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise not_found("Vehicle not found.")

    log_action(
        db,
        user_id=str(admin.id),
        action="DELETE_VEHICLE",
        old_value={"vehicle_id": str(vehicle.id), "plate_number": vehicle.plate_number},
    )
    db.delete(vehicle)
    db.commit()


# ── KM Usage Reporting ────────────────────────────────────

def _build_km_usage(vehicle: Vehicle, db: Session) -> VehicleKmUsageResponse:
    """
    Compute km-usage stats for a single vehicle:
    - Sums km_used for all COMPLETED trips of this vehicle, grouped by driver.
    - Compares total against monthly_km limit and calculates overtime.
    """
    # Aggregate km per driver for this vehicle (only COMPLETED trips with km data)
    rows = (
        db.query(
            Trip.driver_id,
            User.full_name,
            func.sum(Trip.end_odometer - Trip.start_odometer).label("km_sum"),
        )
        .join(User, User.id == Trip.driver_id)
        .filter(
            Trip.vehicle_id == vehicle.id,
            Trip.status == TripStatus.COMPLETED,
            Trip.end_odometer.isnot(None),
        )
        .group_by(Trip.driver_id, User.full_name)
        .all()
    )

    drivers = [
        DriverKmContribution(
            driver_id=row.driver_id,
            driver_name=row.full_name,
            km_used=round(row.km_sum, 2),
        )
        for row in rows
    ]

    total_km_used = round(sum(d.km_used for d in drivers), 2)

    overtime_km: float | None = None
    is_over_limit = False
    if vehicle.monthly_km is not None:
        raw_overtime = total_km_used - vehicle.monthly_km
        overtime_km = round(max(0.0, raw_overtime), 2)
        is_over_limit = overtime_km > 0

    return VehicleKmUsageResponse(
        vehicle_id=vehicle.id,
        plate_number=vehicle.plate_number,
        make=vehicle.make,
        model=vehicle.model,
        monthly_km_limit=vehicle.monthly_km,
        total_km_used=total_km_used,
        overtime_km=overtime_km,
        is_over_limit=is_over_limit,
        drivers=drivers,
    )


@router.get("/{vehicle_id}/km-usage", response_model=VehicleKmUsageResponse)
def get_vehicle_km_usage(
    vehicle_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Return km-usage statistics for a single vehicle across **all drivers**.

    - `total_km_used`: total completed-trip km for this vehicle (all time).
    - `monthly_km_limit`: the configured monthly allowance (null if not set).
    - `overtime_km`: km beyond the monthly limit; null if no limit is set.
    - `is_over_limit`: true when `overtime_km > 0`.
    - `drivers`: per-driver breakdown of km contribution.
    """
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise not_found("Vehicle not found.")

    return _build_km_usage(vehicle, db)


@router.get("/km-usage/all", response_model=list[VehicleKmUsageResponse])
def list_all_vehicles_km_usage(
    only_over_limit: bool = Query(False, description="If true, only return vehicles that exceeded their monthly km limit"),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Return km-usage statistics for **all vehicles**.

    Use `only_over_limit=true` to filter to vehicles that have exceeded
    their monthly km allowance (i.e. have overtime).
    """
    vehicles = db.query(Vehicle).order_by(Vehicle.plate_number).all()
    results = [_build_km_usage(v, db) for v in vehicles]

    if only_over_limit:
        results = [r for r in results if r.is_over_limit]

    return results
