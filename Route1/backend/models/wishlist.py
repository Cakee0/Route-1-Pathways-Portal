"""
models/wishlist.py — Wishlist ORM models for Route 1.

Organizations create wishlist items that represent donation opportunities.
Each item links to one or more farmers who produce the requested crop.
Consumers see these items on the marketplace and can donate funds so the
farmer ships the crop to the organization for free.
"""

import enum
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Text, Boolean,
    DateTime, Numeric, ForeignKey, Enum,
)
from sqlalchemy.orm import relationship

from database import Base


_MYSQL_ARGS = {
    "mysql_engine":  "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


class WishlistStatusEnum(str, enum.Enum):
    open      = "open"       # still accepting donations
    funded    = "funded"     # fully funded, awaiting delivery
    fulfilled = "fulfilled"  # crop delivered to org
    cancelled = "cancelled"  # org cancelled


class WishlistItem(Base):
    """
    One entry on an organization's wishlist.
    Represents a specific crop the org needs — consumers can donate funds
    to cover the cost so a linked farmer ships it to the org for free.
    """
    __tablename__  = "wishlist_items"
    __table_args__ = _MYSQL_ARGS

    id                    = Column(Integer, primary_key=True, index=True)
    organization_id       = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # What is needed
    crop_name             = Column(String(255), nullable=False, index=True)
    quantity_needed       = Column(String(100), nullable=False)   # e.g. "50"
    quantity_unit         = Column(String(50),  nullable=False, default="lbs")
    total_amount_required = Column(Numeric(10, 2), nullable=False)  # total $ to fund

    # Optional context
    notes                 = Column(Text, nullable=True)

    # State
    status                = Column(
        Enum(WishlistStatusEnum),
        default=WishlistStatusEnum.open,
        nullable=False,
    )
    is_group_donation     = Column(Boolean, default=False, nullable=False)
    amount_donated        = Column(Numeric(10, 2), default=0, nullable=False)

    created_at            = Column(DateTime, default=datetime.utcnow)
    updated_at            = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── Relationships ───────────────────────────────────────────────────────
    organization   = relationship(
        "User",
        foreign_keys=[organization_id],
        back_populates="wishlist_items",
    )
    farmer_links   = relationship(
        "WishlistFarmerLink",
        back_populates="wishlist_item",
        cascade="all, delete-orphan",
    )
    donations      = relationship(
        "Donation",
        back_populates="wishlist_item",
        cascade="all, delete-orphan",
    )
    group_donation = relationship(
        "GroupDonation",
        back_populates="wishlist_item",
        uselist=False,   # one-to-one: a wishlist item has at most one group donation
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<WishlistItem id={self.id} crop={self.crop_name!r} "
            f"org={self.organization_id} status={self.status}>"
        )


class WishlistFarmerLink(Base):
    """
    Association table linking a WishlistItem to one or more Farmers.
    A wishlist item can be fulfilled by any of the linked farmers.
    """
    __tablename__  = "wishlist_farmer_links"
    __table_args__ = _MYSQL_ARGS

    id               = Column(Integer, primary_key=True, index=True)
    wishlist_item_id = Column(Integer, ForeignKey("wishlist_items.id"), nullable=False, index=True)
    farmer_id        = Column(Integer, ForeignKey("users.id"),          nullable=False, index=True)
    created_at       = Column(DateTime, default=datetime.utcnow)

    # ── Relationships ───────────────────────────────────────────────────────
    wishlist_item = relationship("WishlistItem", back_populates="farmer_links")
    farmer        = relationship("User", foreign_keys=[farmer_id])

    def __repr__(self) -> str:
        return (
            f"<WishlistFarmerLink wishlist={self.wishlist_item_id} "
            f"farmer={self.farmer_id}>"
        )
