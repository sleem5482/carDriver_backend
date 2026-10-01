"""
Admin Vehicles router — full CRUD + single vehicle report endpoint.
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from app.dependencies import get_db, require_admin
from app.models.user import User
from app.models.driver_vehicle import DriverVehicleAssignment
from app.models.trip import Trip
from app.models.vehicle import Vehicle, VehicleStatus
from app.schemas.vehicle import (
    VehicleCreate, VehicleUpdate, VehicleResponse, VehicleAvailabilityUpdate,
    VehicleReportResponse, DriverKmSummary, TripBrief, AssignedDriverBrief,
    AssignmentRecord, DriverReport,
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


# ── Vehicle Report ─────────────────────────────────────────

@router.get("/{vehicle_id}/report", response_model=VehicleReportResponse)
def get_vehicle_report(
    vehicle_id: uuid.UUID,
    date_from: date | None = Query(None, description="Filter trips from this date (inclusive)"),
    date_to: date | None = Query(None, description="Filter trips up to this date (inclusive)"),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Full report for a single vehicle.

    Returns:
    - Vehicle info (including monthly km limit)
    - Currently assigned driver
    - Total km used across all drivers (completed trips, within date range)
    - Overtime km if total exceeds monthly_km limit
    - High-level per-driver km breakdown (completed trips only)
    - Per-driver full detail: assignment history + ALL trips (OPEN & COMPLETED)
    - Flat list of all trips (filterable by date_from / date_to)
    """
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise not_found("Vehicle not found.")

    # ── Currently assigned driver ──────────────────────────
    active_assignment = (
        db.query(DriverVehicleAssignment)
        .options(joinedload(DriverVehicleAssignment.driver))
        .filter(
            DriverVehicleAssignment.vehicle_id == vehicle_id,
            DriverVehicleAssignment.is_active == True,
        )
        .first()
    )

    assigned_driver: AssignedDriverBrief | None = None
    if active_assignment and active_assignment.driver:
        d = active_assignment.driver
        assigned_driver = AssignedDriverBrief(
            driver_id=d.id,
            driver_name=d.full_name,
            mobile_number=d.mobile_number,
            assigned_at=active_assignment.assigned_at,
        )

    # ── All assignment records for this vehicle ────────────
    all_assignments = (
        db.query(DriverVehicleAssignment)
        .options(joinedload(DriverVehicleAssignment.driver))
        .filter(DriverVehicleAssignment.vehicle_id == vehicle_id)
        .order_by(DriverVehicleAssignment.assigned_at.desc())
        .all()
    )

    # Build a map: driver_id → {driver info, list of AssignmentRecord, is_currently_assigned}
    driver_assignment_map: dict[uuid.UUID, dict] = {}
    for asgn in all_assignments:
        if asgn.driver is None:
            continue
        did = asgn.driver_id
        if did not in driver_assignment_map:
            driver_assignment_map[did] = {
                "driver_id": did,
                "driver_name": asgn.driver.full_name,
                "mobile_number": asgn.driver.mobile_number,
                "assignments": [],
                "is_currently_assigned": False,
            }
        driver_assignment_map[did]["assignments"].append(
            AssignmentRecord(
                assigned_at=asgn.assigned_at,
                unassigned_at=asgn.unassigned_at,
                is_active=asgn.is_active,
            )
        )
        if asgn.is_active:
            driver_assignment_map[did]["is_currently_assigned"] = True

    # ── ALL trips for this vehicle (OPEN + COMPLETED) ──────
    all_trips_query = (
        db.query(Trip)
        .options(joinedload(Trip.driver))
        .filter(Trip.vehicle_id == vehicle_id)
    )

    if date_from:
        all_trips_query = all_trips_query.filter(Trip.start_date >= date_from)
    if date_to:
        all_trips_query = all_trips_query.filter(Trip.start_date <= date_to)

    all_trips_db = all_trips_query.order_by(Trip.start_date.desc()).all()

    # ── Build flat TripBrief list (all statuses) ───────────
    trip_briefs: list[TripBrief] = []
    for t in all_trips_db:
        trip_briefs.append(TripBrief(
            trip_id=t.id,
            driver_id=t.driver_id,
            driver_name=t.driver.full_name if t.driver else "Unknown",
            start_date=t.start_date,
            start_location=t.start_location,
            end_location=t.end_location,
            start_odometer=t.start_odometer,
            end_odometer=t.end_odometer,
            km_used=t.km_used,
            working_hours_formatted=t.working_hours_formatted,
            status=t.status.value,
            verification_status=t.verification_status.value,
        ))

    # ── Per-driver trip grouping ───────────────────────────
    driver_trips_map: dict[uuid.UUID, list[TripBrief]] = {}
    for brief in trip_briefs:
        driver_trips_map.setdefault(brief.driver_id, []).append(brief)

    # Add drivers who only have trips but no formal assignment record
    for t in all_trips_db:
        if t.driver is None or t.driver_id in driver_assignment_map:
            continue
        driver_assignment_map[t.driver_id] = {
            "driver_id": t.driver_id,
            "driver_name": t.driver.full_name,
            "mobile_number": t.driver.mobile_number,
            "assignments": [],
            "is_currently_assigned": False,
        }

    # ── Per-driver km aggregation (completed trips only) ───
    driver_km: dict[uuid.UUID, dict] = {}
    for t in all_trips_db:
        if t.driver is None or t.km_used is None:
            continue
        if t.driver_id not in driver_km:
            driver_km[t.driver_id] = {
                "driver_id": t.driver_id,
                "driver_name": t.driver.full_name,
                "total_km": 0.0,
                "trip_count": 0,
            }
        driver_km[t.driver_id]["total_km"] += t.km_used
        driver_km[t.driver_id]["trip_count"] += 1

    driver_summaries = [
        DriverKmSummary(
            driver_id=v["driver_id"],
            driver_name=v["driver_name"],
            total_km=round(v["total_km"], 2),
            trip_count=v["trip_count"],
        )
        for v in sorted(driver_km.values(), key=lambda x: x["total_km"], reverse=True)
    ]

    # ── Build DriverReport list ────────────────────────────
    driver_reports: list[DriverReport] = []
    for did, info in driver_assignment_map.items():
        km_data = driver_km.get(did, {"total_km": 0.0, "trip_count": 0})
        driver_reports.append(DriverReport(
            driver_id=info["driver_id"],
            driver_name=info["driver_name"],
            mobile_number=info["mobile_number"],
            assignments=info["assignments"],
            is_currently_assigned=info["is_currently_assigned"],
            total_km=round(km_data["total_km"], 2),
            trip_count=len(driver_trips_map.get(did, [])),
            trips=driver_trips_map.get(did, []),
        ))

    # Sort: currently assigned first, then by total_km descending
    driver_reports.sort(key=lambda r: (not r.is_currently_assigned, -r.total_km))

    # ── Total km + overtime (completed trips) ──────────────
    total_km_used = round(sum(d.total_km for d in driver_summaries), 2)

    overtime_km: float | None = None
    is_over_limit = False
    if vehicle.monthly_km is not None:
        raw_overtime = total_km_used - vehicle.monthly_km
        overtime_km = round(max(0.0, raw_overtime), 2)
        is_over_limit = overtime_km > 0

    return VehicleReportResponse(
        vehicle_id=vehicle.id,
        plate_number=vehicle.plate_number,
        vehicle_type=vehicle.vehicle_type,
        make=vehicle.make,
        model=vehicle.model,
        category=vehicle.category,
        status=vehicle.status,
        monthly_km_limit=vehicle.monthly_km,
        assigned_driver=assigned_driver,
        date_from=date_from,
        date_to=date_to,
        total_km_used=total_km_used,
        overtime_km=overtime_km,
        is_over_limit=is_over_limit,
        drivers=driver_summaries,
        driver_reports=driver_reports,
        trips=trip_briefs,
    )

