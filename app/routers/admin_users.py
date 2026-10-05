"""
Admin Users router — full CRUD.
When creating/editing a driver, the response includes available vehicles for assignment.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_admin
from app.models.user import User, UserRole
from app.models.vehicle import Vehicle, VehicleStatus
from app.models.driver_vehicle import DriverVehicleAssignment
from app.models.trip import Trip
from app.schemas.user import (
    UserCreate, UserUpdate, UserResponse, UserListResponse, VehicleBrief,
)
from app.services.auth_service import hash_password
from app.services.audit_service import log_action
from app.utils.exceptions import not_found, conflict

router = APIRouter(prefix="/admin/users", tags=["Admin – Users"])


# ── Helpers ───────────────────────────────────────────────

def _get_assigned_vehicle(db: Session, driver_id: uuid.UUID) -> Vehicle | None:
    """Return the currently assigned vehicle for a driver, or None."""
    assignment = (
        db.query(DriverVehicleAssignment)
        .filter(
            DriverVehicleAssignment.driver_id == driver_id,
            DriverVehicleAssignment.is_active == True,
        )
        .first()
    )
    return assignment.vehicle if assignment else None


def _get_available_vehicles(db: Session) -> list[Vehicle]:
    """Return all vehicles with AVAILABLE status."""
    return db.query(Vehicle).filter(Vehicle.status == VehicleStatus.AVAILABLE).all()


def _build_user_response(db: Session, user: User) -> UserResponse:
    """Build a UserResponse with assigned vehicle and available vehicles list.

    The `available_vehicles` list contains:
    - All AVAILABLE vehicles (unassigned)
    - The vehicle currently assigned to THIS driver (so it still appears in the edit-form dropdown)
    """
    assigned = _get_assigned_vehicle(db, user.id)
    available = _get_available_vehicles(db)

    # If the driver already has an assigned vehicle it will be ASSIGNED status,
    # so it won't appear in the AVAILABLE-only list above. Add it explicitly so
    # the frontend edit-form can still display/keep the current selection.
    if assigned and not any(v.id == assigned.id for v in available):
        available = [assigned] + available

    return UserResponse(
        id=user.id,
        full_name=user.full_name,
        mobile_number=user.mobile_number,
        email=user.email,
        role=user.role,
        status=user.status,
        notes=user.notes,
        generated_code=user.generated_code,
        created_at=user.created_at,
        updated_at=user.updated_at,
        assigned_vehicle=VehicleBrief.model_validate(assigned) if assigned else None,
        available_vehicles=[VehicleBrief.model_validate(v) for v in available],
    )


def _assign_vehicle(db: Session, driver_id: uuid.UUID, vehicle_id: uuid.UUID, admin_id: str):
    """Assign a vehicle to a driver, deactivating any prior assignment."""
    # Capture the current active assignment BEFORE deactivating it
    old_assignment = (
        db.query(DriverVehicleAssignment)
        .filter(
            DriverVehicleAssignment.driver_id == driver_id,
            DriverVehicleAssignment.is_active == True,
        )
        .first()
    )

    if old_assignment:
        old_assignment.is_active = False
        old_assignment.unassigned_at = datetime.now(timezone.utc)
        # Free the old vehicle only if it's different from the one being assigned
        if old_assignment.vehicle_id != vehicle_id:
            db.query(Vehicle).filter(Vehicle.id == old_assignment.vehicle_id).update(
                {"status": VehicleStatus.AVAILABLE}
            )

    # Create new assignment
    new_assignment = DriverVehicleAssignment(
        driver_id=driver_id,
        vehicle_id=vehicle_id,
        is_active=True,
    )
    db.add(new_assignment)

    # Mark vehicle as ASSIGNED
    db.query(Vehicle).filter(Vehicle.id == vehicle_id).update(
        {"status": VehicleStatus.ASSIGNED}
    )

    # Flush so the new assignment row exists in the DB transaction
    # and expire all cached ORM objects (bulk .update() bypasses the identity map,
    # leaving Vehicle objects stale — expire forces a fresh reload on next access).
    db.flush()
    db.expire_all()

    log_action(
        db,
        user_id=admin_id,
        action="ASSIGN_VEHICLE",
        new_value={"driver_id": str(driver_id), "vehicle_id": str(vehicle_id)},
    )


def _unassign_vehicle(db: Session, driver_id: uuid.UUID, admin_id: str):
    """Deactivate the driver's current assignment and free the vehicle."""
    active = (
        db.query(DriverVehicleAssignment)
        .filter(
            DriverVehicleAssignment.driver_id == driver_id,
            DriverVehicleAssignment.is_active == True,
        )
        .first()
    )
    if not active:
        return  # nothing to unassign

    active.is_active = False
    active.unassigned_at = datetime.now(timezone.utc)
    db.query(Vehicle).filter(Vehicle.id == active.vehicle_id).update(
        {"status": VehicleStatus.AVAILABLE}
    )
    # Flush and expire so bulk UPDATE is reflected in the session cache
    db.flush()
    db.expire_all()
    log_action(
        db,
        user_id=admin_id,
        action="UNASSIGN_VEHICLE",
        old_value={"driver_id": str(driver_id), "vehicle_id": str(active.vehicle_id)},
    )


# ── Endpoints ─────────────────────────────────────────────

@router.get("/", response_model=list[UserListResponse])
def list_users(
    role: UserRole | None = Query(None),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """List all users, optionally filtered by role."""
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    return query.order_by(User.created_at.desc()).all()


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Get a single user with assigned vehicle and available vehicles."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise not_found("User not found.")
    return _build_user_response(db, user)


@router.post("/", response_model=UserResponse, status_code=201)
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Create a new user. Optionally assign a vehicle by providing vehicle_id."""
    # Check uniqueness — only check email if one was provided (NULL is always allowed)
    if body.email is not None and db.query(User).filter(User.email == body.email).first():
        raise conflict("Email already registered.")
    if db.query(User).filter(User.mobile_number == body.mobile_number).first():
        raise conflict("Mobile number already registered.")

    import random
    raw_password = body.password
    generated_code = None
    if not raw_password:
        raw_password = f"{random.randint(0, 999999):06d}"
        generated_code = raw_password

    user = User(
        full_name=body.full_name,
        mobile_number=body.mobile_number,
        email=body.email,
        hashed_password=hash_password(raw_password),
        generated_code=generated_code,
        role=body.role,
        status=body.status,
        notes=body.notes,
    )
    db.add(user)
    db.flush()

    # Vehicle assignment
    if body.vehicle_id:
        vehicle = db.query(Vehicle).filter(Vehicle.id == body.vehicle_id).first()
        if not vehicle:
            raise not_found("Vehicle not found.")
        if vehicle.status != VehicleStatus.AVAILABLE:
            raise conflict("Vehicle is not available for assignment.")
        _assign_vehicle(db, user.id, body.vehicle_id, str(admin.id))

    log_action(
        db,
        user_id=str(admin.id),
        action="CREATE_USER",
        new_value={"user_id": str(user.id), "role": user.role.value},
    )
    db.commit()
    db.refresh(user)
    return _build_user_response(db, user)


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Update user details. Optionally re-assign a vehicle."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise not_found("User not found.")

    old_values = {
        "full_name": user.full_name,
        "email": user.email,
        "mobile_number": user.mobile_number,
        "role": user.role.value,
        "status": user.status.value,
    }

    # Apply only fields that were explicitly sent.
    # email is special: it CAN be set to None explicitly (to clear it).
    # Other nullable fields (notes) also accept None to clear them.
    update_data = body.model_dump(exclude_unset=True, exclude={"vehicle_id", "password"})
    for field, value in update_data.items():
        setattr(user, field, value)

    # If email was explicitly updated to a non-None value, check uniqueness
    if "email" in update_data and update_data["email"] is not None:
        existing = db.query(User).filter(User.email == update_data["email"], User.id != user_id).first()
        if existing:
            raise conflict("Email already registered.")

    # Password update only if a non-empty string was provided
    if body.password:
        user.hashed_password = hash_password(body.password)

    # Vehicle re-assignment logic — uses model_fields_set to distinguish:
    #   - vehicle_id NOT in request  → do nothing (don't touch assignment)
    #   - vehicle_id: null in request → unassign the current vehicle
    #   - vehicle_id: <uuid> in request → assign/re-assign to that vehicle
    if "vehicle_id" in body.model_fields_set:
        if body.vehicle_id is None:
            # Explicitly sent null → unassign current vehicle
            _unassign_vehicle(db, user.id, str(admin.id))
        else:
            vehicle = db.query(Vehicle).filter(Vehicle.id == body.vehicle_id).first()
            if not vehicle:
                raise not_found("Vehicle not found.")

            # Reject if explicitly marked unavailable
            if vehicle.status == VehicleStatus.NOT_AVAILABLE:
                raise conflict("Vehicle is marked as not available. Change its status first.")

            # If the vehicle is ASSIGNED, make sure it belongs to THIS driver
            # (re-confirming the same vehicle is fine; assigning another driver's vehicle is not)
            if vehicle.status == VehicleStatus.ASSIGNED:
                other_assignment = (
                    db.query(DriverVehicleAssignment)
                    .filter(
                        DriverVehicleAssignment.vehicle_id == body.vehicle_id,
                        DriverVehicleAssignment.is_active == True,
                        DriverVehicleAssignment.driver_id != user_id,
                    )
                    .first()
                )
                if other_assignment:
                    raise conflict(
                        "Vehicle is currently assigned to another driver. Unassign that driver first."
                    )

            _assign_vehicle(db, user.id, body.vehicle_id, str(admin.id))

    log_action(
        db,
        user_id=str(admin.id),
        action="UPDATE_USER",
        old_value=old_values,
        new_value={k: v for k, v in body.model_dump(exclude_unset=True, mode="json").items() if v is not None},
    )
    db.commit()
    db.refresh(user)
    return _build_user_response(db, user)


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Delete a user and release any assigned vehicle."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise not_found("User not found.")

    # Step 1: Release active vehicle assignments — free the vehicle status back to AVAILABLE
    active_assignments = (
        db.query(DriverVehicleAssignment)
        .filter(
            DriverVehicleAssignment.driver_id == user_id,
            DriverVehicleAssignment.is_active == True,
        )
        .all()
    )
    for assignment in active_assignments:
        db.query(Vehicle).filter(Vehicle.id == assignment.vehicle_id).update(
            {"status": VehicleStatus.AVAILABLE}
        )

    # Step 2: Bulk-delete ALL driver_vehicle_assignments via SQL (not ORM cascade).
    # REASON: lazy="selectin" already loaded these objects into SQLAlchemy's session
    # identity map. When db.delete(user) runs, SQLAlchemy tries to NULL out driver_id
    # on those loaded objects — but driver_id is NOT NULL, causing IntegrityError/500.
    # A direct SQL DELETE bypasses the ORM identity map completely.
    db.query(DriverVehicleAssignment).filter(
        DriverVehicleAssignment.driver_id == user_id
    ).delete(synchronize_session="fetch")

    # Step 3: Bulk-delete all trips for this driver (same ORM identity map issue).
    db.query(Trip).filter(
        Trip.driver_id == user_id
    ).delete(synchronize_session="fetch")

    # Step 4: Log before deleting (audit_logs.user_id will be SET NULL by DB FK cascade)
    log_action(
        db,
        user_id=str(admin.id),
        action="DELETE_USER",
        old_value={"user_id": str(user.id), "full_name": user.full_name},
    )

    # Step 5: Delete the user row
    db.delete(user)
    db.commit()

