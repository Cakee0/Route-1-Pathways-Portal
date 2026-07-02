"""
models/fulfillment.py — Delivery record for a fulfilled wishlist item.

The source of truth for MPCA grant impact metrics. When an organization marks
a wishlist item fulfilled it records the actual pounds of food delivered, so
"pounds rescued" is a plain SUM over this table:

    SELECT SUM(pounds_delivered) FROM fulfillments
    WHERE delivered_at BETWEEN :from AND :to;
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from database import Base


_MYSQL_ARGS = {
    "mysql_engine":  "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


class Fulfillment(Base):
    __tablename__  = "fulfillments"
    __table_args__ = _MYSQL_ARGS

    id                 = Column(Integer, primary_key=True, index=True)
    wishlist_item_id   = Column(Integer, ForeignKey("wishlist_items.id"), nullable=False, index=True)
    organization_id    = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)  # recorder
    farmer_id          = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)  # deliverer

    # Grant metric: actual pounds of food delivered.
    pounds_delivered   = Column(Numeric(12, 2), nullable=False)

    # Optional context in the listing's original unit (e.g. 4 crates).
    quantity_delivered = Column(Numeric(10, 2), nullable=True)
    quantity_unit      = Column(String(50), nullable=True)

    notes              = Column(String(512), nullable=True)
    delivered_at       = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at         = Column(DateTime, default=datetime.utcnow, nullable=False)

    # ── Relationships ───────────────────────────────────────────────────────
    wishlist_item = relationship("WishlistItem", back_populates="fulfillments")
    organization  = relationship("User", foreign_keys=[organization_id])
    farmer        = relationship("User", foreign_keys=[farmer_id])

    def __repr__(self) -> str:
        return (
            f"<Fulfillment id={self.id} wishlist={self.wishlist_item_id} "
            f"lbs={self.pounds_delivered}>"
        )
