"""
models/donation.py — Donation, GroupDonation, and GroupDonationParticipant ORM models.

Flow:
  1. Consumer donates to a WishlistItem → Donation row created.
  2. If the wishlist item is a group donation, a GroupDonation aggregates
     multiple Donations (via GroupDonationParticipant rows).
  3. When the group reaches its goal, all participant donations are confirmed
     and points are awarded.

Points rule: every $20 donated → 100 points (see models/points.py).
"""

import enum
from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, Numeric, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship

from database import Base


_MYSQL_ARGS = {
    "mysql_engine":  "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


# ── Enums ─────────────────────────────────────────────────────────────────────

class DonationStatusEnum(str, enum.Enum):
    pending   = "pending"    # payment initiated, not confirmed
    confirmed = "confirmed"  # payment confirmed, points awarded
    refunded  = "refunded"   # group failed / org cancelled


class GroupDonationStatusEnum(str, enum.Enum):
    open      = "open"       # accepting new participants
    funded    = "funded"     # goal reached, processing payments
    completed = "completed"  # all payments confirmed, crop in transit
    failed    = "failed"     # goal not reached — all donations refunded


# ── Donation ──────────────────────────────────────────────────────────────────

class Donation(Base):
    """
    One consumer's donation toward a wishlist item.
    Money flows: Consumer → Farmer (for the crop cost), then farmer ships
    the crop to the organisation at no extra charge.
    """
    __tablename__  = "donations"
    __table_args__ = _MYSQL_ARGS

    id               = Column(Integer,      primary_key=True, index=True)
    consumer_id      = Column(Integer,      ForeignKey("users.id"),          nullable=False, index=True)
    farmer_id        = Column(Integer,      ForeignKey("users.id"),          nullable=False, index=True)
    wishlist_item_id = Column(Integer,      ForeignKey("wishlist_items.id"), nullable=False, index=True)
    amount           = Column(Numeric(10, 2), nullable=False)
    status           = Column(
        Enum(DonationStatusEnum),
        default=DonationStatusEnum.pending,
        nullable=False,
    )

    # Non-null if participating in a group donation
    group_donation_id = Column(Integer, ForeignKey("group_donations.id"), nullable=True, index=True)

    # Stripe / payment gateway reference (for future real payment integration)
    payment_reference = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── Relationships ───────────────────────────────────────────────────────
    consumer      = relationship("User",         foreign_keys=[consumer_id])
    farmer        = relationship("User",         foreign_keys=[farmer_id])
    wishlist_item = relationship("WishlistItem", back_populates="donations")
    points_entry  = relationship(
        "PointsLedger",
        back_populates="donation",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Donation id={self.id} consumer={self.consumer_id} "
            f"amount={self.amount} status={self.status}>"
        )


# ── Group Donation ─────────────────────────────────────────────────────────────

class GroupDonation(Base):
    """
    Aggregates multiple consumers donating together to fund one WishlistItem.
    tracks pledged amounts and donor counts.
    """
    __tablename__  = "group_donations"
    __table_args__ = _MYSQL_ARGS

    id               = Column(Integer,       primary_key=True, index=True)
    wishlist_item_id = Column(Integer,       ForeignKey("wishlist_items.id"), nullable=False, unique=True)

    total_required   = Column(Numeric(10, 2), nullable=False)   # mirrors wishlist total
    amount_pledged   = Column(Numeric(10, 2), default=0,        nullable=False)
    donors_needed    = Column(Integer,        nullable=False)    # target donor count
    donors_count     = Column(Integer,        default=0,         nullable=False)

    status = Column(
        Enum(GroupDonationStatusEnum),
        default=GroupDonationStatusEnum.open,
        nullable=False,
    )

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── Relationships ───────────────────────────────────────────────────────
    wishlist_item = relationship("WishlistItem", back_populates="group_donation")
    participants  = relationship(
        "GroupDonationParticipant",
        back_populates="group_donation",
        cascade="all, delete-orphan",
    )

    @property
    def amount_remaining(self):
        return float(self.total_required) - float(self.amount_pledged)

    @property
    def donors_remaining(self):
        return max(0, self.donors_needed - self.donors_count)

    def __repr__(self) -> str:
        return (
            f"<GroupDonation id={self.id} wishlist={self.wishlist_item_id} "
            f"pledged={self.amount_pledged}/{self.total_required} "
            f"donors={self.donors_count}/{self.donors_needed}>"
        )


# ── Group Donation Participant ─────────────────────────────────────────────────

class GroupDonationParticipant(Base):
    """
    Links a consumer to a specific GroupDonation with their pledge amount.
    Created when a consumer clicks "Join Group Donation".
    """
    __tablename__  = "group_donation_participants"
    __table_args__ = _MYSQL_ARGS

    id                = Column(Integer,       primary_key=True, index=True)
    group_donation_id = Column(Integer,       ForeignKey("group_donations.id"), nullable=False, index=True)
    consumer_id       = Column(Integer,       ForeignKey("users.id"),           nullable=False, index=True)
    donation_id       = Column(Integer,       ForeignKey("donations.id"),        nullable=True)   # set when confirmed
    amount_pledged    = Column(Numeric(10, 2), nullable=False)
    joined_at         = Column(DateTime,       default=datetime.utcnow)

    # ── Relationships ───────────────────────────────────────────────────────
    group_donation = relationship("GroupDonation", back_populates="participants")
    consumer       = relationship("User",           foreign_keys=[consumer_id])
    donation       = relationship("Donation",       foreign_keys=[donation_id])

    def __repr__(self) -> str:
        return (
            f"<GroupDonationParticipant group={self.group_donation_id} "
            f"consumer={self.consumer_id} pledge={self.amount_pledged}>"
        )
