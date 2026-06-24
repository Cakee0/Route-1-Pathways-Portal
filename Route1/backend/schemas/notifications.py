"""
schemas/notifications.py — Pydantic schemas for notification preferences.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class NotificationPrefsUpdate(BaseModel):
    """
    PATCH payload — any field may be omitted (partial update).
    donation_min_price / donation_max_price are validated so min <= max when
    both are provided.
    """
    donation_notifications_enabled:       Optional[bool]  = None
    donation_min_price:                   Optional[float] = Field(None, ge=0)
    donation_max_price:                   Optional[float] = Field(None, ge=0)
    group_donation_notifications_enabled: Optional[bool]  = None

    @model_validator(mode="after")
    def check_price_range(self) -> "NotificationPrefsUpdate":
        lo = self.donation_min_price
        hi = self.donation_max_price
        if lo is not None and hi is not None and lo > hi:
            raise ValueError("donation_min_price must be ≤ donation_max_price")
        return self


class NotificationPrefsResponse(BaseModel):
    user_id:                               int
    donation_notifications_enabled:        bool
    donation_min_price:                    Optional[float]
    donation_max_price:                    Optional[float]
    group_donation_notifications_enabled:  bool
    updated_at:                            datetime

    model_config = {"from_attributes": True}


class ProfileUpdateRequest(BaseModel):
    """Generic profile update — any field may be omitted."""
    full_name:         Optional[str] = None
    organization_name: Optional[str] = None
    location_city:     Optional[str] = None
    location_region:   Optional[str] = None
    phone:             Optional[str] = None


class ProfileUpdateResponse(BaseModel):
    id:                int
    email:             str
    user_type:         str
    full_name:         Optional[str]
    organization_name: Optional[str]
    location_city:     Optional[str]
    location_region:   Optional[str]
    phone:             Optional[str]

    model_config = {"from_attributes": True}
