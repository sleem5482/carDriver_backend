"""
Admin Vehicles router — full CRUD.
"""

import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_admin
from app.models.user import User
from app.models.vehicle import Vehicle
from app.schemas.vehicle import VehicleCreate, VehicleUpdate, VehicleResponse
from app.services.audit_service import log_action
from app.utils.exceptions import not_found, conflict

router = APIRouter(prefix="/admin/vehicles", tags=["Admin – Vehicles"])


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
    """Create a new vehicle."""
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
    """Update vehicle details."""
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise not_found("Vehicle not found.")

    old_values = {
        "vehicle_type": vehicle.vehicle_type,
        "make": vehicle.make,
        "model": vehicle.model,
        "plate_number": vehicle.plate_number,
        "category": vehicle.category,
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
