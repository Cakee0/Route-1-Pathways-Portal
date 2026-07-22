"""
routers/listings.py — Listing-centric browse endpoints.

The org/consumer dashboard shows one card per crop listing (not per farmer).
GET /listings returns the flat, filterable list; GET /listings/{id} powers
the listing detail page (full listing + farmer attribution).
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import FarmerCropInventory, User
from routers.auth import get_current_user
from routers.organizations import _query_available_crops
from schemas.browse import FarmerPublicInfo, ListingCardResponse, ListingDetailResponse

router = APIRouter(prefix="/listings", tags=["Listings"])


# ── GET /listings ─────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=List[ListingCardResponse],
    summary="Browse individual crop listings (flat, newest first)",
)
def browse_listings(
    crop_type:       Optional[str]   = Query(None, description="Partial match on crop name"),
    location_region: Optional[str]   = Query(None, description="Minnesota region"),
    location_city:   Optional[str]   = Query(None, description="Minnesota city"),
    min_price:       Optional[float] = Query(None, description="Min price per unit"),
    max_price:       Optional[float] = Query(None, description="Max price per unit"),
    has_transport:   Optional[bool]  = Query(None, description="Farmer can provide transport"),
    donation_only:   Optional[bool]  = Query(None, description="Only donation-eligible listings"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[ListingCardResponse]:
    crops = _query_available_crops(
        db, crop_type, location_region, location_city,
        min_price, max_price, has_transport, donation_only,
    )
    crops.sort(key=lambda c: c.created_at, reverse=True)

    return [
        ListingCardResponse(
            id                    = c.id,
            crop_name             = c.crop_name,
            quantity_available    = c.quantity_available,
            quantity_unit         = c.quantity_unit,
            price_per_unit        = c.price_per_unit,
            description           = c.description,
            can_provide_transport = c.can_provide_transport,
            needs_transport       = c.needs_transport,
            donation_eligible     = c.donation_eligible,
            farmer_id             = c.farmer.id,
            farmer_name           = c.farmer.full_name or c.farmer.organization_name,
            farm_name             = c.farmer.organization_name,
            farmer_avatar_url     = c.farmer.avatar_url,
            location_city         = c.farmer.location_city,
            location_region       = c.farmer.location_region,
        )
        for c in crops
    ]


# ── GET /listings/{listing_id} ────────────────────────────────────────────────

@router.get(
    "/{listing_id}",
    response_model=ListingDetailResponse,
    summary="Get one crop listing with its farmer's info",
)
def get_listing(
    listing_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ListingDetailResponse:
    crop = (
        db.query(FarmerCropInventory)
        .options(joinedload(FarmerCropInventory.farmer))
        .filter(FarmerCropInventory.id == listing_id)
        .first()
    )

    farmer = crop.farmer if crop else None
    if not crop or not crop.is_available or not farmer or not farmer.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found or no longer available.",
        )

    return ListingDetailResponse(
        id                    = crop.id,
        crop_name             = crop.crop_name,
        quantity_available    = crop.quantity_available,
        quantity_unit         = crop.quantity_unit,
        price_per_unit        = crop.price_per_unit,
        description           = crop.description,
        can_provide_transport = crop.can_provide_transport,
        needs_transport       = crop.needs_transport,
        donation_eligible     = crop.donation_eligible,
        is_available          = crop.is_available,
        created_at            = crop.created_at,
        updated_at            = crop.updated_at,
        farmer                = FarmerPublicInfo.model_validate(farmer),
    )
