"""
models/user.py — User ORM model for Route 1.

Three user roles are supported:
  farmer       — lists available / surplus crops
  organization — restaurant, grocery store, or food shelf; browses farmer listings
  consumer     — individual (chef, family, caterer); browses farmer listings
"""

import enum
from datetime import datetime

from sqlalchemy import (
    Column, Integer, SmallInteger, String, Text, Boolean, DateTime, Enum,
)
from sqlalchemy.orm import relationship

from database import Base


# ── Enums ────────────────────────────────────────────────────────────────────

class UserTypeEnum(str, enum.Enum):
    farmer       = "farmer"
    organization = "organization"
    consumer     = "consumer"


class OrgSubtypeEnum(str, enum.Enum):
    restaurant    = "restaurant"
    grocery_store = "grocery_store"
    food_shelf    = "food_shelf"


# ── MySQL table options ───────────────────────────────────────────────────────

_MYSQL_ARGS = {
    "mysql_engine":  "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


# ── Table: users ─────────────────────────────────────────────────────────────

class User(Base):
    __tablename__  = "users"
    __table_args__ = _MYSQL_ARGS

    id               = Column(Integer, primary_key=True, index=True)
    email            = Column(String(255), unique=True, index=True, nullable=False)
    # Nullable: accounts created via "Sign in with Google" have no password.
    hashed_password  = Column(String(255), nullable=True)
    # Google account subject id ("sub"); set when a user links / signs in with Google.
    google_id        = Column(String(255), unique=True, index=True, nullable=True)

    # Role
    user_type        = Column(Enum(UserTypeEnum), nullable=False)
    org_subtype      = Column(Enum(OrgSubtypeEnum), nullable=True)  # organizations only

    # Profile
    full_name         = Column(String(255), nullable=True)
    organization_name = Column(String(255), nullable=True)   # org / farm name
    location_city     = Column(String(100), nullable=True)   # Minnesota city
    location_region   = Column(String(100), nullable=True)   # MN region (e.g. Twin Cities Metro)
    phone             = Column(String(30),  nullable=True)

    # The human layer — what makes a listing a person rather than a row.
    # All optional: an empty profile renders an initials avatar, never a gap.
    avatar_url        = Column(String(512), nullable=True)   # full URL (S3), NULL → initials
    tagline           = Column(String(140), nullable=True)   # one line under the name
    bio               = Column(Text,        nullable=True)   # the story, in their own words
    year_started      = Column(SmallInteger, nullable=True)  # → "Growing since 1994"
    is_active         = Column(Boolean, default=True)
    created_at        = Column(DateTime,  default=datetime.utcnow)

    # Relationships
    crop_listings = relationship(
        "FarmerCropInventory",
        back_populates="farmer",
        cascade="all, delete-orphan",
    )
    sent_messages = relationship(
        "Message",
        foreign_keys="Message.sender_id",
        back_populates="sender",
    )
    received_messages = relationship(
        "Message",
        foreign_keys="Message.receiver_id",
        back_populates="receiver",
    )
    # Organization wishlist items
    wishlist_items = relationship(
        "WishlistItem",
        foreign_keys="WishlistItem.organization_id",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    # Consumer notification preferences (1-to-1)
    notification_prefs = relationship(
        "NotificationPreferences",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} type={self.user_type}>"
