"""
Admin Trips router — list & detail with filtering.
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from app.dependencies import get_db, require_admin
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.trip import Trip, TripStatus, VerificationStatus
from app.schemas.trip import TripListResponse, TripDetailResponse, DriverBrief, VehicleBrief

router = APIRouter(prefix="/admin/trips", tags=["Admin – Trips"])


@router.get("/", response_model=list[TripListResponse])
def list_trips(
    date_from: date | None = Query(None, description="Filter trips starting from this date"),
    date_to: date | None = Query(None, description="Filter trips up to this date"),
    driver_id: uuid.UUID | None = Query(None),
    vehicle_id: uuid.UUID | None = Query(None),
    plate_number: str | None = Query(None),
    status: TripStatus | None = Query(None),
    verification_status: VerificationStatus | None = Query(None),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Retrieve all trips with optional query filters.
    Supports filtering by: date range, driver, vehicle, plate number, status, exception type.
    """
    query = db.query(Trip).options(joinedload(Trip.driver), joinedload(Trip.vehicle))

    if date_from:
        query = query.filter(Trip.start_date >= date_from)
    if date_to:
        query = query.filter(Trip.start_date <= date_to)
    if driver_id:
        query = query.filter(Trip.driver_id == driver_id)
    if vehicle_id:
        query = query.filter(Trip.vehicle_id == vehicle_id)
    if plate_number:
        query = query.join(Vehicle).filter(Vehicle.plate_number.ilike(f"%{plate_number}%"))
    if status:
        query = query.filter(Trip.status == status)
    if verification_status:
        query = query.filter(Trip.verification_status == verification_status)

    trips = query.order_by(Trip.created_at.desc()).all()

    results = []
    for trip in trips:
        results.append(
            TripListResponse(
                id=trip.id,
                driver=DriverBrief.model_validate(trip.driver),
                vehicle=VehicleBrief.model_validate(trip.vehicle),
                start_date=trip.start_date,
                start_location=trip.start_location,
                end_location=trip.end_location,
                start_odometer=trip.start_odometer,
                end_odometer=trip.end_odometer,
                status=trip.status,
                verification_status=trip.verification_status,
                route_notes=trip.route_notes,
                start_odometer_image=trip.start_odometer_image,
                end_odometer_image=trip.end_odometer_image,
                km_used=trip.km_used,
                working_hours=trip.working_hours,
                working_hours_formatted=trip.working_hours_formatted,
                overtime_hours=trip.overtime_hours,
                created_at=trip.created_at,
            )
        )
    return results


@router.get("/{trip_id}", response_model=TripDetailResponse)
def get_trip(
    trip_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Retrieve comprehensive trip details including Driver, Vehicle,
    Start/End metrics, Total KM, and Working Hours.
    """
    trip = (
        db.query(Trip)
        .options(joinedload(Trip.driver), joinedload(Trip.vehicle))
        .filter(Trip.id == trip_id)
        .first()
    )
    if not trip:
        from app.utils.exceptions import not_found
        raise not_found("Trip not found.")

    return TripDetailResponse(
        id=trip.id,
        driver=DriverBrief.model_validate(trip.driver),
        vehicle=VehicleBrief.model_validate(trip.vehicle),
        start_date=trip.start_date,
        start_server_time=trip.start_server_time,
        start_latitude=trip.start_latitude,
        start_longitude=trip.start_longitude,
        start_location=trip.start_location,
        start_odometer=trip.start_odometer,
        start_odometer_image=trip.start_odometer_image,
        end_date=trip.end_date,
        end_server_time=trip.end_server_time,
        end_latitude=trip.end_latitude,
        end_longitude=trip.end_longitude,
        end_location=trip.end_location,
        end_odometer=trip.end_odometer,
        end_odometer_image=trip.end_odometer_image,
        km_used=trip.km_used,
        working_hours=trip.working_hours,
        working_hours_formatted=trip.working_hours_formatted,
        overtime_hours=trip.overtime_hours,
        route_notes=trip.route_notes,
        status=trip.status,
        verification_status=trip.verification_status,
        exception_reason=trip.exception_reason,
        created_at=trip.created_at,
        updated_at=trip.updated_at,
    )
