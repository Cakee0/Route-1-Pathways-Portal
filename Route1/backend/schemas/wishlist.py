"""
schemas/wishlist.py — Pydantic schemas for WishlistItem endpoints.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from models import WishlistStatusEnum
from schemas.units import QuantityUnit


# ── Farmer summary embedded in wishlist responses ────────────────────────────

class FarmerSummary(BaseModel):
    farmer_id:   int
    full_name:   Optional[str]
    farm_name:   Optional[str]   # organization_name used as farm name for farmers
    location_city: Optional[str]

    model_config = {"from_attributes": True}


# ── Group-donation snapshot embedded in wishlist responses ───────────────────

class GroupDonationSummary(BaseModel):
    id:               int
    total_required:   float
    amount_pledged:   float
    amount_remaining: float
    donors_needed:    int
    donors_count:     int
    donors_remaining: int
    status:           str

    model_config = {"from_attributes": True}


# ── Create ────────────────────────────────────────────────────────────────────

class WishlistItemCreate(BaseModel):
    crop_name:             str          = Field(..., min_length=1, max_length=255)
    # Numeric so impact totals can be aggregated (MPCA reporting).
    quantity_needed:       Decimal      = Field(..., gt=0)
    quantity_unit:         QuantityUnit = "lbs"
    total_amount_required: float        = Field(..., gt=0, description="Total $ needed to fund this item")
    notes:                 Optional[str] = None
    is_group_donation:     bool          = False
    farmer_ids:            List[int]     = Field(..., min_length=1, description="At least one farmer must be linked")
    # For group donations — how many donors are expected
    donors_needed:         Optional[int] = Field(None, ge=2, description="Required when is_group_donation=True")


class WishlistItemUpdate(BaseModel):
    crop_name:             Optional[str]     = Field(None, min_length=1, max_length=255)
    quantity_needed:       Optional[Decimal] = Field(None, gt=0)
    quantity_unit:         Optional[QuantityUnit] = None
    total_amount_required: Optional[float] = Field(None, gt=0)
    notes:                 Optional[str]   = None
    status:                Optional[WishlistStatusEnum] = None
    farmer_ids:            Optional[List[int]] = Field(None, min_length=1)

    @field_validator("status")
    @classmethod
    def only_cancellable_via_patch(
        cls, v: Optional[WishlistStatusEnum]
    ) -> Optional[WishlistStatusEnum]:
        """`funded` is set by the donation flow and `fulfilled` must go through
        POST /wishlist/{id}/fulfill so pounds delivered are always recorded."""
        if v is not None and v != WishlistStatusEnum.cancelled:
            raise ValueError(
                "Only status='cancelled' may be set directly. "
                "Use POST /wishlist/{id}/fulfill to mark an item fulfilled."
            )
        return v


# ── Response ──────────────────────────────────────────────────────────────────

class WishlistItemResponse(BaseModel):
    id:                    int
    organization_id:       int
    organization_name:     Optional[str]
    crop_name:             str
    # float so JSON carries a number: 200, not "200.00".
    quantity_needed:       float
    quantity_unit:         str
    total_amount_required: float
    amount_donated:        float
    notes:                 Optional[str]
    status:                WishlistStatusEnum
    is_group_donation:     bool
    farmers:               List[FarmerSummary] = []
    group_donation:        Optional[GroupDonationSummary] = None
    created_at:            datetime
    updated_at:            datetime

    model_config = {"from_attributes": True}


# ── Fulfillment (delivery recording — MPCA impact metrics) ────────────────────

class FulfillmentCreate(BaseModel):
    """Body for POST /wishlist/{item_id}/fulfill.

    `pounds_delivered` is the grant metric and is always required, regardless
    of the unit the listing was displayed in.
    """
    farmer_id:          int
    pounds_delivered:   Decimal = Field(..., gt=0, description="Actual pounds of food delivered")
    quantity_delivered: Optional[Decimal] = Field(None, gt=0, description="Optional: amount in the listing's unit")
    quantity_unit:      Optional[QuantityUnit] = None
    notes:              Optional[str] = Field(None, max_length=512)
    delivered_at:       Optional[datetime] = Field(None, description="Defaults to now")


class FulfillmentResponse(BaseModel):
    id:                 int
    wishlist_item_id:   int
    organization_id:    int
    farmer_id:          int
    pounds_delivered:   float
    quantity_delivered: Optional[float]
    quantity_unit:      Optional[str]
    notes:              Optional[str]
    delivered_at:       datetime
    created_at:         datetime

    model_config = {"from_attributes": True}
