"""
routers/organizations.py — Browse endpoints for organization accounts.

Organizations (restaurants, grocery stores, food shelves) can search for
farmers with available crops using optional filters.

The shared _browse_farmers_impl() helper is re-used by consumers.py.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import FarmerCropInventory, User, UserTypeEnum
from routers.auth import get_current_user
from schemas.browse import CropSummary, FarmerListingResponse

router = APIRouter(prefix="/organizations", tags=["Organizations"])


# ── GET /organizations/browse ─────────────────────────────────────────────────

@router.get(
    "/browse",
    response_model=List[FarmerListingResponse],
    summary="Browse farmers with available crops (organization view)",
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


# ── Shared browse logic (also used by consumers and listings routers) ────────

def _query_available_crops(
    db: Session,
    crop_type: Optional[str],
    location_region: Optional[str],
    location_city: Optional[str],
    min_price: Optional[float],
    max_price: Optional[float],
    has_transport: Optional[bool],
    donation_only: Optional[bool],
) -> List[FarmerCropInventory]:
    """
    Build and execute a crop inventory query with optional filters.
    Returns the flat list of available listings (farmer relationship loaded),
    excluding listings whose farmer is missing/inactive or fails the
    location filters.
    """
    # joinedload avoids a lazy-load query per farmer below (browse is the
    # hottest endpoint — this was a 1+N pattern)
    crop_q = (
        db.query(FarmerCropInventory)
        .options(joinedload(FarmerCropInventory.farmer))
        .filter(FarmerCropInventory.is_available == True)  # noqa: E712
    )

    if crop_type:
        crop_q = crop_q.filter(FarmerCropInventory.crop_name.ilike(f"%{crop_type}%"))
    if min_price is not None:
        crop_q = crop_q.filter(FarmerCropInventory.price_per_unit >= min_price)
    if max_price is not None:
        crop_q = crop_q.filter(FarmerCropInventory.price_per_unit <= max_price)
    if has_transport is not None:
        crop_q = crop_q.filter(
            FarmerCropInventory.can_provide_transport == has_transport  # noqa: E712
        )
    if donation_only:
        crop_q = crop_q.filter(
            FarmerCropInventory.donation_eligible == True  # noqa: E712
        )

    # Location filters live on the farmer, not the listing
    results: List[FarmerCropInventory] = []
    for crop in crop_q.all():
        farmer: User = crop.farmer
        if not farmer or not farmer.is_active:
            continue
        if location_region and (farmer.location_region or "").lower() != location_region.lower():
            continue
        if location_city and (farmer.location_city or "").lower() != location_city.lower():
            continue
        results.append(crop)

    return results


def _browse_farmers_impl(
    db: Session,
    crop_type: Optional[str],
    location_region: Optional[str],
    location_city: Optional[str],
    min_price: Optional[float],
    max_price: Optional[float],
    has_transport: Optional[bool],
    donation_only: Optional[bool],
) -> List[FarmerListingResponse]:
    """
    Run the filtered crop query, then group results by farmer and return
    FarmerListingResponse objects.
    """
    crops = _query_available_crops(
        db, crop_type, location_region, location_city,
        min_price, max_price, has_transport, donation_only,
    )

    # Group crops by farmer
    farmer_map: dict = {}
    for crop in crops:
        farmer: User = crop.farmer
        if farmer.id not in farmer_map:
            farmer_map[farmer.id] = {"farmer": farmer, "crops": []}
        farmer_map[farmer.id]["crops"].append(crop)

    results: List[FarmerListingResponse] = []
    for entry in farmer_map.values():
        f: User = entry["farmer"]
        summaries = [
            CropSummary(
                id                    = c.id,
                crop_name             = c.crop_name,
                quantity_available    = c.quantity_available,
                quantity_unit         = c.quantity_unit,
                price_per_unit        = c.price_per_unit,
                can_provide_transport = c.can_provide_transport,
                needs_transport       = c.needs_transport,
                donation_eligible     = c.donation_eligible,
            )
            for c in entry["crops"]
        ]
        results.append(
            FarmerListingResponse(
                id                = f.id,
                full_name         = f.full_name,
                organization_name = f.organization_name,
                location_city     = f.location_city,
                location_region   = f.location_region,
                phone             = f.phone,
                crop_count        = len(summaries),
                crops             = summaries,
            )
        )

    return results
