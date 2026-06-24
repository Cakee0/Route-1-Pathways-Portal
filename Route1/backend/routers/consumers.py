"""
routers/consumers.py — Browse endpoints for consumer accounts.

Consumers (chefs, families, caterers) have the same browse filters as
organizations and additionally can filter by bulk vs small quantities.
The browsing logic itself is shared via organizations._browse_farmers_impl.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from models import User
from routers.auth import get_current_user
from routers.organizations import _browse_farmers_impl
from schemas.browse import FarmerListingResponse

router = APIRouter(prefix="/consumers", tags=["Consumers"])


@router.get(
    "/browse",
    response_model=List[FarmerListingResponse],
    summary="Browse farmers with available crops (consumer view)",
)
def browse_farmers(
    crop_type:       Optional[str]   = Query(None, description="Partial match on crop name"),
    location_region: Optional[str]   = Query(None, description="Minnesota region"),
    location_city:   Optional[str]   = Query(None, description="Minnesota city"),
    min_price:       Optional[float] = Query(None, description="Min price per unit"),
    max_price:       Optional[float] = Query(None, description="Max price per unit"),
    has_transport:   Optional[bool]  = Query(None, description="Farmer can provide transport"),
    donation_only:   Optional[bool]  = Query(None, description="Only donation-eligible listings"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[FarmerListingResponse]:
    return _browse_farmers_impl(
        db, crop_type, location_region, location_city,
        min_price, max_price, has_transport, donation_only,
    )
