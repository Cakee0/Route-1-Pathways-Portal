"""
models/crop_inventory.py — Farmer crop inventory ORM model.

Each row represents one crop item a farmer has available or in excess.
Farmers control visibility via `is_available`, pricing, transport options,
and whether the crop is eligible for food-shelf donation.
"""

from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Text, Boolean,
    DateTime, Numeric, ForeignKey,
)
from sqlalchemy.orm import relationship

from database import Base


_MYSQL_ARGS = {
    "mysql_engine":  "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


class FarmerCropInventory(Base):
    __tablename__  = "farmer_crop_inventory"
    __table_args__ = _MYSQL_ARGS

    id                    = Column(Integer, primary_key=True, index=True)
    farmer_id             = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Crop details
    crop_name             = Column(String(255),   nullable=False, index=True)
    quantity_available    = Column(String(100),   nullable=False)   # e.g. "200"
    quantity_unit         = Column(String(50),    nullable=False, default="lbs")
    price_per_unit        = Column(Numeric(10, 2), nullable=True)   # NULL = price on request
    description           = Column(Text,          nullable=True)

    # Logistics flags
    can_provide_transport = Column(Boolean, default=False, nullable=False)
    needs_transport       = Column(Boolean, default=False, nullable=False)

    # Eligibility
    donation_eligible     = Column(Boolean, default=False, nullable=False)
    is_available          = Column(Boolean, default=True,  nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    farmer = relationship("User", back_populates="crop_listings")

    def __repr__(self) -> str:
        return (
            f"<FarmerCropInventory id={self.id} crop={self.crop_name!r} "
            f"farmer_id={self.farmer_id}>"
        )
