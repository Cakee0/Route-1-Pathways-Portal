"""
schemas/wishlist.py — Pydantic schemas for WishlistItem endpoints.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from models import WishlistStatusEnum


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
    quantity_needed:       str          = Field(..., min_length=1, max_length=100)
    quantity_unit:         str          = Field("lbs", max_length=50)
    total_amount_required: float        = Field(..., gt=0, description="Total $ needed to fund this item")
    notes:                 Optional[str] = None
    is_group_donation:     bool          = False
    farmer_ids:            List[int]     = Field(..., min_length=1, description="At least one farmer must be linked")
    # For group donations — how many donors are expected
    donors_needed:         Optional[int] = Field(None, ge=2, description="Required when is_group_donation=True")


class WishlistItemUpdate(BaseModel):
    crop_name:             Optional[str]   = None
    quantity_needed:       Optional[str]   = None
    quantity_unit:         Optional[str]   = None
    total_amount_required: Optional[float] = Field(None, gt=0)
    notes:                 Optional[str]   = None
    status:                Optional[WishlistStatusEnum] = None
    farmer_ids:            Optional[List[int]] = None


# ── Response ──────────────────────────────────────────────────────────────────

class WishlistItemResponse(BaseModel):
    id:                    int
    organization_id:       int
    organization_name:     Optional[str]
    crop_name:             str
    quantity_needed:       str
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
