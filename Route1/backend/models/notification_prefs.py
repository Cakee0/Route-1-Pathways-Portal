"""
models/notification_prefs.py — Per-user notification preference settings.

Each user gets at most one row in this table (1-to-1 with users).
Consumers have donation + group-donation preferences with optional price ranges.
"""

from datetime import datetime

from sqlalchemy import Column, Integer, Boolean, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from database import Base


_MYSQL_ARGS = {
    "mysql_engine":  "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


class NotificationPreferences(Base):
    """
    Stores per-user notification toggles.

    donation_notifications_enabled: True → notify consumer when a new donation
        opportunity falls within [donation_min_price, donation_max_price].
    group_donation_notifications_enabled: True → notify consumer when:
        - a new group donation is created
        - a group donation needs only one more donor
        - a group donation's per-share amount matches their price range
    """
    __tablename__  = "notification_preferences"
    __table_args__ = _MYSQL_ARGS

    id      = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)

    # ── Consumer: donation notifications ───────────────────────────────────
    donation_notifications_enabled   = Column(Boolean, default=False, nullable=False)
    donation_min_price               = Column(Numeric(10, 2), nullable=True)  # NULL = no lower bound
    donation_max_price               = Column(Numeric(10, 2), nullable=True)  # NULL = no upper bound

    # ── Consumer: group donation notifications ──────────────────────────────
    group_donation_notifications_enabled = Column(Boolean, default=False, nullable=False)

    # ── Timestamps ──────────────────────────────────────────────────────────
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── Relationship back to user ───────────────────────────────────────────
    user = relationship("User", back_populates="notification_prefs")

    def __repr__(self) -> str:
        return (
            f"<NotificationPreferences user={self.user_id} "
            f"donation={self.donation_notifications_enabled} "
            f"group={self.group_donation_notifications_enabled}>"
        )
