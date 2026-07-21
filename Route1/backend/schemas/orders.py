"""
schemas/orders.py — Pydantic schemas for the direct crop-purchase flow.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from models import OrderStatusEnum, DeliveryMethodEnum


class OrderCreateRequest(BaseModel):
    """
    Consumer requests to buy a quantity of a crop and proposes who delivers.
    delivery_address is required when the farmer delivers; for pickup it may be
    omitted (the router fills a sensible default).
    """
    crop_id:          int
    quantity:         float = Field(..., gt=0, description="How much to buy, in the listing's unit")
    delivery_method:  DeliveryMethodEnum = DeliveryMethodEnum.farmer_delivers
    delivery_name:    str   = Field(..., min_length=1, max_length=255)
    delivery_address: Optional[str] = None
    delivery_phone:   Optional[str] = Field(None, max_length=30)
    delivery_notes:   Optional[str] = None


class OrderResponse(BaseModel):
    id:               int
    consumer_id:      int
    consumer_name:    Optional[str] = None
    farmer_id:        int
    farmer_name:      Optional[str] = None
    crop_id:          int
    crop_name:        str
    quantity:         float
    quantity_unit:    str
    unit_price:       float
    total_amount:     float
    currency:         str
    delivery_method:  DeliveryMethodEnum
    delivery_name:    str
    delivery_address: str
    delivery_phone:   Optional[str] = None
    delivery_notes:   Optional[str] = None
    status:           OrderStatusEnum
    created_at:       datetime

    model_config = {"from_attributes": True}


class OrderCheckoutResponse(BaseModel):
    """Returned when an approved order is paid — redirect the browser to checkout_url."""
    order_id:     int
    checkout_url: str
    status:       OrderStatusEnum
