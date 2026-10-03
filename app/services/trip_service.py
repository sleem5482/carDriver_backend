"""
Trip service — business logic for starting/ending trips and exception detection.

Overtime logic
--------------
When a trip is completed and the vehicle has a `daily_shift_hours` limit:
1. Query all *completed* trips for the same vehicle on the same calendar date.
2. Sum their working hours (including the trip being completed right now).
3. overtime_hours = max(0, total_day_hours - daily_shift_hours)

The value is stored on the Trip row so it can be queried and reported later.
"""

from sqlalchemy.orm import Session

from app.models.trip import Trip, TripStatus, VerificationStatus
from app.models.vehicle import Vehicle


def get_open_trip(db: Session, driver_id: str) -> Trip | None:
    """Return the driver's currently OPEN trip, or None."""
    return (
        db.query(Trip)
        .filter(Trip.driver_id == driver_id, Trip.status == TripStatus.OPEN)
        .first()
    )


def detect_exceptions(trip: Trip) -> list[str]:
    """
    Check the completed trip for exception conditions.

    Returns a list of exception reason strings (empty = no exceptions).
    """
    reasons: list[str] = []

    # Rule 1: End KM < Start KM
    if trip.end_odometer is not None and trip.end_odometer < trip.start_odometer:
        reasons.append(
            f"End odometer ({trip.end_odometer}) is less than start odometer ({trip.start_odometer})."
        )

    return reasons


def apply_exceptions(trip: Trip) -> None:
    """
    Run exception detection on a trip and update its verification_status accordingly.
    """
    reasons = detect_exceptions(trip)
    if reasons:
        trip.verification_status = VerificationStatus.EXCEPTION
        trip.exception_reason = " | ".join(reasons)
    else:
        trip.verification_status = VerificationStatus.PENDING_REVIEW


def compute_overtime(db: Session, trip: Trip) -> None:
    """
    Calculate overtime_hours for a just-completed trip.

    Steps:
    1. Load the vehicle to get its daily_shift_hours limit.
    2. If no limit is set, leave overtime_hours = None.
    3. Sum working_hours of all OTHER completed trips for the same vehicle
       on the same calendar date (start_date).
    4. Add this trip's own working_hours.
    5. overtime_hours = max(0, total - daily_shift_hours), stored on the trip.

    Call this function AFTER the trip's end fields (end_server_time etc.)
    have been set but BEFORE db.commit().
    """
    vehicle: Vehicle | None = db.query(Vehicle).filter(Vehicle.id == trip.vehicle_id).first()

    if vehicle is None or vehicle.daily_shift_hours is None:
        trip.overtime_hours = None
        return

    shift_limit = vehicle.daily_shift_hours

    # Sum hours from other completed trips on the same vehicle+date
    other_trips = (
        db.query(Trip)
        .filter(
            Trip.vehicle_id == trip.vehicle_id,
            Trip.start_date == trip.start_date,
            Trip.status == TripStatus.COMPLETED,
            Trip.id != trip.id,           # exclude self (not yet committed)
        )
        .all()
    )

    prior_hours: float = sum(
        (t.working_hours or 0.0) for t in other_trips
    )

    this_hours: float = trip.working_hours or 0.0
    total_day_hours = prior_hours + this_hours

    raw_overtime = total_day_hours - shift_limit
    trip.overtime_hours = round(max(0.0, raw_overtime), 2)
