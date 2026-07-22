"""
schemas/browse.py — Response schemas used by the org/consumer browse endpoints.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel


class CropSummary(BaseModel):
    """Compact crop card embedded within a FarmerListingResponse."""
    id:                    int
    crop_name:             str
    # float so JSON carries a number: 200, not "200.00".
    quantity_available:    float
    quantity_unit:         str
    price_per_unit:        Optional[Decimal]
    can_provide_transport: bool
    needs_transport:       bool
    donation_eligible:     bool

    model_config = {"from_attributes": True}


class FarmerListingResponse(BaseModel):
    """Farmer card shown in browse / search results."""
    id:                int
    full_name:         Optional[str]
    organization_name: Optional[str]   # farm / business name
    location_city:     Optional[str]
    location_region:   Optional[str]
    phone:             Optional[str]
    crop_count:        int
    crops:             List[CropSummary]

    model_config = {"from_attributes": True}


class ListingCardResponse(BaseModel):
    """One listing card in the browse grid — a crop listing with farmer attribution."""
    id:                    int
    crop_name:             str
    # float so JSON carries a number: 200, not "200.00".
    quantity_available:    float
    quantity_unit:         str
    price_per_unit:        Optional[Decimal]   # None → "price on request"
    description:           Optional[str]
    can_provide_transport: bool
    needs_transport:       bool
    donation_eligible:     bool
    farmer_id:             int
    farmer_name:           Optional[str]
    farm_name:             Optional[str]   # farmer's organization_name
    farmer_avatar_url:     Optional[str] = None   # NULL → card renders initials
    location_city:         Optional[str]
    location_region:       Optional[str]

    model_config = {"from_attributes": True}


class FarmerPublicInfo(BaseModel):
    """
    Farmer block embedded in a listing detail response.

    Carries the profile fields too, so the detail page can introduce a person
    (face, tagline, story) without a second round-trip.
    """
    id:                int
    full_name:         Optional[str]
    organization_name: Optional[str]   # farm / business name
    avatar_url:        Optional[str] = None
    tagline:           Optional[str] = None
    bio:               Optional[str] = None
    year_started:      Optional[int] = None
    location_city:     Optional[str]
    location_region:   Optional[str]
    phone:             Optional[str]

    model_config = {"from_attributes": True}


class ListingDetailResponse(BaseModel):
    """Full crop listing plus its farmer, for the listing detail page."""
    id:                    int
    crop_name:             str
    quantity_available:    float
    quantity_unit:         str
    price_per_unit:        Optional[Decimal]   # None → "price on request"
    description:           Optional[str]
    can_provide_transport: bool
    needs_transport:       bool
    donation_eligible:     bool
    is_available:          bool
    created_at:            datetime
    updated_at:            datetime
    farmer:                FarmerPublicInfo

    model_config = {"from_attributes": True}
