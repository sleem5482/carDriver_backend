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
    """Build a UserResponse with assigned vehicle and available vehicles list."""
    assigned = _get_assigned_vehicle(db, user.id)
    available = _get_available_vehicles(db)

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
    # Deactivate current assignment for this driver
    db.query(DriverVehicleAssignment).filter(
        DriverVehicleAssignment.driver_id == driver_id,
        DriverVehicleAssignment.is_active == True,
    ).update({
        "is_active": False,
        "unassigned_at": datetime.now(timezone.utc),
    })

    # Set old vehicle back to AVAILABLE
    old_assignment = (
        db.query(DriverVehicleAssignment)
        .filter(
            DriverVehicleAssignment.driver_id == driver_id,
            DriverVehicleAssignment.is_active == False,
        )
        .order_by(DriverVehicleAssignment.unassigned_at.desc())
        .first()
    )
    if old_assignment:
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

    log_action(
        db,
        user_id=admin_id,
        action="ASSIGN_VEHICLE",
        new_value={"driver_id": str(driver_id), "vehicle_id": str(vehicle_id)},
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
    # Check uniqueness
    if db.query(User).filter(User.email == body.email).first():
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

    # Apply updates
    update_data = body.model_dump(exclude_unset=True, exclude={"vehicle_id", "password"})
    for field, value in update_data.items():
        setattr(user, field, value)

    if body.password is not None:
        user.hashed_password = hash_password(body.password)

    # Vehicle re-assignment
    if body.vehicle_id is not None:
        vehicle = db.query(Vehicle).filter(Vehicle.id == body.vehicle_id).first()
        if not vehicle:
            raise not_found("Vehicle not found.")
        if vehicle.status not in (VehicleStatus.AVAILABLE, VehicleStatus.ASSIGNED):
            raise conflict("Vehicle is not available for assignment.")
        _assign_vehicle(db, user.id, body.vehicle_id, str(admin.id))

    log_action(
        db,
        user_id=str(admin.id),
        action="UPDATE_USER",
        old_value=old_values,
        new_value=body.model_dump(exclude_unset=True),
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

    # Release assigned vehicle
    active_assignments = (
        db.query(DriverVehicleAssignment)
        .filter(
            DriverVehicleAssignment.driver_id == user_id,
            DriverVehicleAssignment.is_active == True,
        )
        .all()
    )
    for assignment in active_assignments:
        assignment.is_active = False
        assignment.unassigned_at = datetime.now(timezone.utc)
        db.query(Vehicle).filter(Vehicle.id == assignment.vehicle_id).update(
            {"status": VehicleStatus.AVAILABLE}
        )

    log_action(
        db,
        user_id=str(admin.id),
        action="DELETE_USER",
        old_value={"user_id": str(user.id), "full_name": user.full_name},
    )
    db.delete(user)
    db.commit()
