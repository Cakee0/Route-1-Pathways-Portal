"""
models.py — SQLAlchemy ORM models (maps to MySQL tables in mysqlRouteOne)
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean,
    DateTime, Enum, ForeignKey,
)
from sqlalchemy.orm import relationship
from database import Base
import enum


# ── Enum types ──────────────────────────────────────────────────────────────
class UserTypeEnum(str, enum.Enum):
    organization = "organization"
    farmer       = "farmer"
    donor        = "donor"          # future expansion


class FulfillmentStatusEnum(str, enum.Enum):
    pending    = "pending"
    matched    = "matched"
    fulfilled  = "fulfilled"


# ── MySQL table defaults (InnoDB + full-Unicode charset for AWS RDS) ────────
_MYSQL_ARGS = {
    "mysql_engine":  "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


# ── Table 1 : users ─────────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"
    __table_args__ = _MYSQL_ARGS

    id            = Column(Integer, primary_key=True, index=True)
    email         = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    user_type     = Column(Enum(UserTypeEnum), nullable=False)

    # Profile fields
    full_name     = Column(String(255),  nullable=True)
    organization_name = Column(String(255), nullable=True)  # for orgs
    address       = Column(String(512),  nullable=True)
    city          = Column(String(100),  nullable=True)
    state         = Column(String(100),  nullable=True)
    zip_code      = Column(String(20),   nullable=True)
    phone         = Column(String(30),   nullable=True)
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime, default=datetime.utcnow)

    # Relationships
    crop_requests = relationship("CropRequest", back_populates="organization")

    def __repr__(self):
        return f"<User id={self.id} email={self.email} type={self.user_type}>"


# ── Table 2 : crop_requests ──────────────────────────────────────────────────
class CropRequest(Base):
    __tablename__ = "crop_requests"
    __table_args__ = _MYSQL_ARGS

    id                  = Column(Integer, primary_key=True, index=True)
    organization_id     = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Predefined low-stock crops stored as comma-separated values
    # e.g. "lettuce,tomatoes"
    crops_low_in_stock  = Column(String(512), nullable=False, default="")

    # Freeform nice-to-have crops
    nice_to_have_crops  = Column(Text, nullable=True)

    fulfillment_status  = Column(
        Enum(FulfillmentStatusEnum),
        default=FulfillmentStatusEnum.pending,
        nullable=False,
    )
    created_at          = Column(DateTime, default=datetime.utcnow)
    updated_at          = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    organization        = relationship("User", back_populates="crop_requests")

    def __repr__(self):
        return (
            f"<CropRequest id={self.id} "
            f"org={self.organization_id} "
            f"status={self.fulfillment_status}>"
        )
