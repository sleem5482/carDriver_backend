"""
Trip service — business logic for starting/ending trips and exception detection.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.trip import Trip, TripStatus, VerificationStatus

settings = get_settings()


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

    # Rule 2: Weak GPS accuracy at start
    if trip.start_gps_accuracy > settings.GPS_ACCURACY_THRESHOLD:
        reasons.append(
            f"Start GPS accuracy ({trip.start_gps_accuracy}m) exceeds threshold ({settings.GPS_ACCURACY_THRESHOLD}m)."
        )

    # Rule 3: Weak GPS accuracy at end
    if trip.end_gps_accuracy is not None and trip.end_gps_accuracy > settings.GPS_ACCURACY_THRESHOLD:
        reasons.append(
            f"End GPS accuracy ({trip.end_gps_accuracy}m) exceeds threshold ({settings.GPS_ACCURACY_THRESHOLD}m)."
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
