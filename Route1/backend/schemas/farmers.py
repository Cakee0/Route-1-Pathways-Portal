"""
schemas/farmers.py — Pydantic models for farmer crop inventory CRUD.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, field_validator


class CropListingCreate(BaseModel):
    crop_name:             str
    quantity_available:    str             # e.g. "200"
    quantity_unit:         str   = "lbs"  # lbs, kg, boxes, bushels, etc.
    price_per_unit:        Optional[Decimal] = None  # None = "price on request"
    description:           Optional[str]     = None
    can_provide_transport: bool = False
    needs_transport:       bool = False
    donation_eligible:     bool = False

    @field_validator("crop_name")
    @classmethod
    def normalise_crop_name(cls, v: str) -> str:
        return v.strip().title()

    @field_validator("quantity_available")
    @classmethod
    def quantity_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("quantity_available cannot be empty.")
        return v.strip()

    model_config = {"from_attributes": True}


class CropListingUpdate(BaseModel):
    """All fields optional — PATCH semantics via model_dump(exclude_unset=True)."""
    crop_name:             Optional[str]     = None
    quantity_available:    Optional[str]     = None
    quantity_unit:         Optional[str]     = None
    price_per_unit:        Optional[Decimal] = None
    description:           Optional[str]     = None
    can_provide_transport: Optional[bool]    = None
    needs_transport:       Optional[bool]    = None
    donation_eligible:     Optional[bool]    = None
    is_available:          Optional[bool]    = None

    model_config = {"from_attributes": True}


class CropListingResponse(BaseModel):
    id:                    int
    farmer_id:             int
    crop_name:             str
    quantity_available:    str
    quantity_unit:         str
    price_per_unit:        Optional[Decimal]
    description:           Optional[str]
    can_provide_transport: bool
    needs_transport:       bool
    donation_eligible:     bool
    is_available:          bool
    created_at:            datetime
    updated_at:            datetime

    model_config = {"from_attributes": True}
