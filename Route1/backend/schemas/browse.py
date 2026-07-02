"""
schemas/browse.py — Response schemas used by the org/consumer browse endpoints.
"""

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
