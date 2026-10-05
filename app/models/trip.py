"""
Trip model — tracks driver trips with server-generated timestamps.
Odometer images stored as Cloudinary URLs (String columns).
KM Used and Working Hours are computed hybrid properties.
overtimeHours is computed on trip completion when the vehicle has a
daily_shift_hours limit and stored as a DB column.
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
    driver_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True
    )

    # ── Snapshot Fields (for when driver/vehicle is deleted) ──
    driver_name_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    driver_mobile_snapshot: Mapped[str | None] = mapped_column(String(20), nullable=True)
    vehicle_plate_snapshot: Mapped[str | None] = mapped_column(String(30), nullable=True)
    vehicle_make_snapshot: Mapped[str | None] = mapped_column(String(100), nullable=True)
    vehicle_model_snapshot: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # ── Start Fields ──────────────────────────────────────
    start_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    start_server_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    start_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    start_longitude: Mapped[float] = mapped_column(Float, nullable=False)
    start_location: Mapped[str] = mapped_column(String(255), nullable=False)
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
    end_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    end_odometer: Mapped[float | None] = mapped_column(Float, nullable=True)
    end_odometer_image: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="Cloudinary secure_url"
    )
    route_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    overtime_hours: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Hours worked beyond the vehicle daily shift limit on this trip's date. "
                "NULL if no shift limit is set on the vehicle."
    )

    # ── Status ────────────────────────────────────────────
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
        """Human-readable duration, e.g. '1h 30m 15s', '45m 10s', '2h', '30s'. None while trip is open."""
        if self.end_server_time is None or self.start_server_time is None:
            return None
        total_seconds = int((self.end_server_time - self.start_server_time).total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        parts: list[str] = []
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        if seconds or not parts:
            parts.append(f"{seconds}s")
        return " ".join(parts)

    def __repr__(self) -> str:
        return f"<Trip {self.id} driver={self.driver_id} status={self.status.value}>"
