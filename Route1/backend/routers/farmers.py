"""
routers/farmers.py — Crop inventory CRUD endpoints (farmer role only).

Farmers can add, list, update, and remove their own crop listings.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from database import get_db
from models import FarmerCropInventory, User, UserTypeEnum
from routers.auth import get_current_user
from schemas import CropListingCreate, CropListingResponse, CropListingUpdate

router = APIRouter(prefix="/farmers", tags=["Farmers"])


def _require_farmer(user: User) -> None:
    if user.user_type != UserTypeEnum.farmer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only farmer accounts can perform this action.",
        )


# ── GET /farmers/search ─────────────────────────────────────────────────────

@router.get(
    "/search",
    summary="Search farmers by name or city (for wishlist linking)",
)
def search_farmers(
    q: Optional[str] = Query(None, description="Partial match on name or city"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns a lightweight list of all active farmer users whose
    full_name, organization_name, or location_city matches the
    search term (case-insensitive partial match).
    Any authenticated user can call this endpoint.
    """
    farmer_q = db.query(User).filter(
        User.user_type == UserTypeEnum.farmer,
        User.is_active == True,  # noqa: E712
    )
    if q:
        pattern = f"%{q}%"
        farmer_q = farmer_q.filter(
            or_(
                User.full_name.ilike(pattern),
                User.organization_name.ilike(pattern),
                User.location_city.ilike(pattern),
                User.location_region.ilike(pattern),
            )
        )
    farmers = farmer_q.order_by(User.full_name, User.organization_name).limit(50).all()
    return [
        {
            "id":                f.id,
            "full_name":         f.full_name,
            "organization_name": f.organization_name,
            "location_city":     f.location_city,
            "location_region":   f.location_region,
        }
        for f in farmers
    ]


# ── POST /farmers/crops ───────────────────────────────────────────────────────

@router.post(
    "/crops",
    response_model=CropListingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Farmer adds a new crop listing",
)
def add_crop(
    payload: CropListingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_farmer(current_user)
    crop = FarmerCropInventory(
        farmer_id             = current_user.id,
        crop_name             = payload.crop_name,
        quantity_available    = payload.quantity_available,
        quantity_unit         = payload.quantity_unit,
        price_per_unit        = payload.price_per_unit,
        description           = payload.description,
        can_provide_transport = payload.can_provide_transport,
        needs_transport       = payload.needs_transport,
        donation_eligible     = payload.donation_eligible,
    )
    db.add(crop)
    db.commit()
    db.refresh(crop)
    return crop


# ── GET /farmers/crops ────────────────────────────────────────────────────────

@router.get(
    "/crops",
    response_model=List[CropListingResponse],
    summary="List all crop listings belonging to the current farmer",
)
def list_my_crops(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_farmer(current_user)
    return (
        db.query(FarmerCropInventory)
        .filter(FarmerCropInventory.farmer_id == current_user.id)
        .order_by(FarmerCropInventory.created_at.desc())
        .all()
    )


# ── PUT /farmers/crops/{crop_id} ──────────────────────────────────────────────

@router.put(
    "/crops/{crop_id}",
    response_model=CropListingResponse,
    summary="Update a specific crop listing",
)
def update_crop(
    crop_id: int,
    payload: CropListingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_farmer(current_user)
    crop = (
        db.query(FarmerCropInventory)
        .filter(
            FarmerCropInventory.id == crop_id,
            FarmerCropInventory.farmer_id == current_user.id,
        )
        .first()
    )
    if not crop:
        raise HTTPException(status_code=404, detail="Crop listing not found.")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(crop, field, value)

    db.commit()
    db.refresh(crop)
    return crop


# ── DELETE /farmers/crops/{crop_id} ──────────────────────────────────────────

@router.delete(
    "/crops/{crop_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a crop listing",
)
def delete_crop(
    crop_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_farmer(current_user)
    crop = (
        db.query(FarmerCropInventory)
        .filter(
            FarmerCropInventory.id == crop_id,
            FarmerCropInventory.farmer_id == current_user.id,
        )
        .first()
    )
    if not crop:
        raise HTTPException(status_code=404, detail="Crop listing not found.")

    db.delete(crop)
    db.commit()
