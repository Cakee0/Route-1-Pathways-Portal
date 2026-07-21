"""
models/order.py — CropOrder ORM model (direct consumer purchase of a crop).

Flow (distinct from the donation flow):
  1. Consumer requests to buy a quantity of a crop listing and provides a
     delivery address → CropOrder created with status `pending_farmer`.
  2. Farmer approves (→ `approved`) or declines (→ `declined`).
  3. Once approved, the consumer pays via Stripe Checkout → the webhook
     confirms it (→ `paid`) and decrements the crop's available quantity.

Money is platform-collected (all funds land in Route 1's Stripe account; the
farmer is paid out manually), matching the donation flow. Direct purchases do
NOT earn reward points — points are reserved for charitable contributions.
"""

import enum
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Text, Numeric, DateTime, ForeignKey, Enum,
)
from sqlalchemy.orm import relationship

from database import Base


_MYSQL_ARGS = {
    "mysql_engine":  "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


class OrderStatusEnum(str, enum.Enum):
    pending_farmer = "pending_farmer"  # awaiting the farmer's approval
    approved       = "approved"        # farmer approved; awaiting payment
    paid           = "paid"            # payment confirmed; inventory decremented
    declined       = "declined"        # farmer declined the request
    cancelled      = "cancelled"       # consumer cancelled before paying
    refunded       = "refunded"        # paid then refunded (future)


class DeliveryMethodEnum(str, enum.Enum):
    farmer_delivers = "farmer_delivers"  # farmer brings it to the delivery address
    consumer_pickup = "consumer_pickup"  # consumer collects it from the farmer


class CropOrder(Base):
    """One consumer's direct purchase of a farmer's crop listing."""
    __tablename__  = "crop_orders"
    __table_args__ = _MYSQL_ARGS

    id          = Column(Integer, primary_key=True, index=True)
    consumer_id = Column(Integer, ForeignKey("users.id"),                 nullable=False, index=True)
    farmer_id   = Column(Integer, ForeignKey("users.id"),                 nullable=False, index=True)
    crop_id     = Column(Integer, ForeignKey("farmer_crop_inventory.id"), nullable=False, index=True)

    # Snapshot of price/quantity at request time (the listing may change later).
    quantity      = Column(Numeric(10, 2), nullable=False)
    quantity_unit = Column(String(50),     nullable=False, default="lbs")
    unit_price    = Column(Numeric(10, 2), nullable=False)
    total_amount  = Column(Numeric(10, 2), nullable=False)
    currency      = Column(String(3),      nullable=False, default="usd")

    # Delivery details captured at request time.
    delivery_name    = Column(String(255), nullable=False)
    delivery_address = Column(Text,        nullable=False)
    delivery_phone   = Column(String(30),  nullable=True)
    delivery_notes   = Column(Text,        nullable=True)

    # Who moves the crop — proposed by the consumer, confirmed by the farmer's approval.
    delivery_method  = Column(
        Enum(DeliveryMethodEnum),
        default=DeliveryMethodEnum.farmer_delivers,
        nullable=False,
    )

    status = Column(
        Enum(OrderStatusEnum),
        default=OrderStatusEnum.pending_farmer,
        nullable=False,
        index=True,
    )

    # Stripe references (set when the consumer pays after approval).
    stripe_session_id        = Column(String(255), nullable=True, unique=True)
    stripe_payment_intent_id = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── Relationships ───────────────────────────────────────────────────────
    consumer = relationship("User", foreign_keys=[consumer_id])
    farmer   = relationship("User", foreign_keys=[farmer_id])
    crop     = relationship("FarmerCropInventory", foreign_keys=[crop_id])

    def __repr__(self) -> str:
        return (
            f"<CropOrder id={self.id} consumer={self.consumer_id} "
            f"crop={self.crop_id} qty={self.quantity} status={self.status}>"
        )
