"""
models/points.py — Points ledger ORM model.

Points accumulation rule:
  Every $20 donated = 100 points.

Reward tiers (visual only — rewards TBD):
  500 pts   → Tier 1
  1,500 pts → Tier 2
  3,000 pts → Tier 3
"""

from datetime import datetime

from sqlalchemy import Column, Integer, Numeric, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from database import Base


_MYSQL_ARGS = {
    "mysql_engine":  "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}

# Points per $20 donated
POINTS_PER_UNIT  = 100
DOLLARS_PER_UNIT = 20.0

# Reward tier thresholds (points)
TIER_THRESHOLDS = (500, 1500, 3000)


def calculate_points(donation_amount: float) -> int:
    """Return points earned for a given donation amount (floor division by $20)."""
    units = int(donation_amount // DOLLARS_PER_UNIT)
    return units * POINTS_PER_UNIT


class PointsLedger(Base):
    """
    Immutable ledger recording every points-earning event for a consumer.
    One row per confirmed Donation.
    """
    __tablename__  = "points_ledger"
    __table_args__ = _MYSQL_ARGS

    id           = Column(Integer,       primary_key=True, index=True)
    consumer_id  = Column(Integer,       ForeignKey("users.id"),    nullable=False, index=True)
    donation_id  = Column(Integer,       ForeignKey("donations.id"), nullable=False, unique=True)
    points       = Column(Integer,       nullable=False)
    amount_basis = Column(Numeric(10, 2), nullable=False)  # donation amount used to compute points
    description  = Column(String(512),   nullable=True)    # human-readable reason
    created_at   = Column(DateTime,      default=datetime.utcnow)

    # ── Relationships ───────────────────────────────────────────────────────
    consumer = relationship("User",     foreign_keys=[consumer_id])
    donation = relationship("Donation", back_populates="points_entry")

    def __repr__(self) -> str:
        return (
            f"<PointsLedger id={self.id} consumer={self.consumer_id} "
            f"points={self.points} donation={self.donation_id}>"
        )
