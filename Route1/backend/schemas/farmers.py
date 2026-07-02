"""
schemas/farmers.py — Pydantic models for farmer crop inventory CRUD.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from schemas.units import QuantityUnit


class CropListingCreate(BaseModel):
    crop_name:             str = Field(..., min_length=1, max_length=255)
    # Numeric so impact totals can be aggregated (MPCA reporting).
    quantity_available:    Decimal = Field(..., gt=0)
    quantity_unit:         QuantityUnit = "lbs"
    price_per_unit:        Optional[Decimal] = None  # None = "price on request"
    description:           Optional[str]     = None
    can_provide_transport: bool = False
    needs_transport:       bool = False
    donation_eligible:     bool = False

    @field_validator("crop_name")
    @classmethod
    def normalise_crop_name(cls, v: str) -> str:
        return v.strip().title()

    model_config = {"from_attributes": True}


class CropListingUpdate(BaseModel):
    """All fields optional — PATCH semantics via model_dump(exclude_unset=True)."""
    crop_name:             Optional[str]     = Field(None, min_length=1, max_length=255)
    quantity_available:    Optional[Decimal] = Field(None, gt=0)
    quantity_unit:         Optional[QuantityUnit] = None
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
    # float (not Decimal) so JSON carries a number: 200, not "200.00".
    quantity_available:    float
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
