"""
User model — supports ADMIN and DRIVER roles.
Login username is replaced with email (requirement override).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Enum as SAEnum, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.database import Base


# ── Enums ─────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    DRIVER = "DRIVER"


class UserStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


# ── Model ─────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mobile_number: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, index=True
    )
    email: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True, index=True
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    generated_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role", create_constraint=True),
        nullable=False,
        default=UserRole.DRIVER,
    )
    status: Mapped[UserStatus] = mapped_column(
        SAEnum(UserStatus, name="user_status", create_constraint=True),
        nullable=False,
        default=UserStatus.ACTIVE,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # ── Relationships ─────────────────────────────────────
    vehicle_assignments = relationship(
        "DriverVehicleAssignment", back_populates="driver", lazy="selectin",
        passive_deletes=True,
    )
    trips = relationship(
        "Trip", back_populates="driver", lazy="selectin",
        passive_deletes=True,
    )
    audit_logs = relationship(
        "AuditLog", back_populates="user", lazy="selectin",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<User {self.full_name} ({self.role.value})>"
