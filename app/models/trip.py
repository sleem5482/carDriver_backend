"""
Trip model — tracks driver trips with server-generated timestamps.
Odometer images stored as Cloudinary URLs (String columns).
KM Used and Working Hours are computed hybrid properties.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    String, Float, Text, DateTime, Enum as SAEnum, ForeignKey, Date,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.database import Base


# ── Enums ─────────────────────────────────────────────────

class TripStatus(str, enum.Enum):
    OPEN = "OPEN"
    COMPLETED = "COMPLETED"


class VerificationStatus(str, enum.Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    VERIFIED = "VERIFIED"
    EXCEPTION = "EXCEPTION"
    REJECTED = "REJECTED"


# ── Model ─────────────────────────────────────────────────

class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── Foreign Keys ──────────────────────────────────────
    driver_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False
    )

    # ── Start Fields ──────────────────────────────────────
    start_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    start_server_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    start_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    start_longitude: Mapped[float] = mapped_column(Float, nullable=False)
    start_gps_accuracy: Mapped[float] = mapped_column(Float, nullable=False)
    start_odometer: Mapped[float] = mapped_column(Float, nullable=False)
    start_odometer_image: Mapped[str] = mapped_column(
        String(512), nullable=False, comment="Cloudinary secure_url"
    )

    # ── End Fields (nullable until trip is completed) ─────
    end_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    end_server_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    end_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    end_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    end_gps_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    end_odometer: Mapped[float | None] = mapped_column(Float, nullable=True)
    end_odometer_image: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="Cloudinary secure_url"
    )

    # ── Notes & Status ────────────────────────────────────
    route_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[TripStatus] = mapped_column(
        SAEnum(TripStatus, name="trip_status", create_constraint=True),
        nullable=False,
        default=TripStatus.OPEN,
    )
    verification_status: Mapped[VerificationStatus] = mapped_column(
        SAEnum(VerificationStatus, name="verification_status", create_constraint=True),
        nullable=False,
        default=VerificationStatus.PENDING_REVIEW,
    )
    exception_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Timestamps ────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # ── Relationships ─────────────────────────────────────
    driver = relationship("User", back_populates="trips")
    vehicle = relationship("Vehicle", back_populates="trips")

    # ── Computed Properties ───────────────────────────────

    @hybrid_property
    def km_used(self) -> float | None:
        """End Odometer − Start Odometer.  None while trip is open."""
        if self.end_odometer is not None and self.start_odometer is not None:
            return round(self.end_odometer - self.start_odometer, 2)
        return None

    @hybrid_property
    def working_hours(self) -> float | None:
        """End Server Time − Start Server Time in hours.  None while trip is open."""
        if self.end_server_time is not None and self.start_server_time is not None:
            delta = self.end_server_time - self.start_server_time
            return round(delta.total_seconds() / 3600, 2)
        return None

    @property
    def working_hours_formatted(self) -> str | None:
        """Human-readable duration, e.g. '1h 30m', '45m', '2h'. None while trip is open."""
        if self.end_server_time is None or self.start_server_time is None:
            return None
        total_minutes = int((self.end_server_time - self.start_server_time).total_seconds() // 60)
        hours, minutes = divmod(total_minutes, 60)
        if hours and minutes:
            return f"{hours}h {minutes}m"
        if hours:
            return f"{hours}h"
        return f"{minutes}m"

    def __repr__(self) -> str:
        return f"<Trip {self.id} driver={self.driver_id} status={self.status.value}>"
