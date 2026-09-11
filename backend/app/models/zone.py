"""MonitoringZone model — user-defined geographic zones for targeted surveillance."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MonitoringZone(Base):
    """A user-defined geographic surveillance zone with custom alert sensitivity."""

    __tablename__ = "monitoring_zones"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    min_lat: Mapped[float] = mapped_column(Float, nullable=False)
    max_lat: Mapped[float] = mapped_column(Float, nullable=False)
    min_lon: Mapped[float] = mapped_column(Float, nullable=False)
    max_lon: Mapped[float] = mapped_column(Float, nullable=False)

    sensitivity: Mapped[str] = mapped_column(
        String(20), nullable=False, default="normal", doc="critical, high, normal"
    )
    alert_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        Index("idx_zones_active", "is_active"),
        Index("idx_zones_bbox", "min_lat", "max_lat", "min_lon", "max_lon"),
    )

    def contains(self, lat: float, lon: float) -> bool:
        """Check whether the given coordinates fall within the zone's bounding box."""
        return (
            self.min_lat <= lat <= self.max_lat
            and self.min_lon <= lon <= self.max_lon
        )
