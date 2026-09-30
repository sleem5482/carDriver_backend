"""
Vehicle model.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Enum as SAEnum, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.database import Base


# ── Enums ─────────────────────────────────────────────────

class VehicleStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    ASSIGNED = "ASSIGNED"
    NOT_AVAILABLE = "NOT_AVAILABLE"


# ── Model ─────────────────────────────────────────────────

class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    vehicle_type: Mapped[str] = mapped_column(String(100), nullable=False)
    make: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    plate_number: Mapped[str] = mapped_column(
        String(30), unique=True, nullable=False, index=True
    )
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[VehicleStatus] = mapped_column(
        SAEnum(VehicleStatus, name="vehicle_status", create_constraint=True),
        nullable=False,
        default=VehicleStatus.AVAILABLE,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # ── Relationships ─────────────────────────────────────
    assignments = relationship(
        "DriverVehicleAssignment", back_populates="vehicle", lazy="selectin"
    )
    trips = relationship("Trip", back_populates="vehicle", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Vehicle {self.plate_number} ({self.make} {self.model})>"
