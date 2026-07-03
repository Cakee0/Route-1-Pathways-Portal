"""
routers/wishlist.py — Wishlist CRUD endpoints.

Organizations can create and manage wishlist items.
Consumers (and everyone authenticated) can browse active wishlist items
as donation opportunities on the marketplace dashboard.

POST   /wishlist/               — org creates a wishlist item
GET    /wishlist/               — browse all open wishlist items (consumer marketplace feed)
GET    /wishlist/mine           — org lists its own wishlist items
GET    /wishlist/{item_id}      — detail for a single item
PATCH  /wishlist/{item_id}      — org updates its own item
DELETE /wishlist/{item_id}      — org soft-cancels its item
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import (
    User, UserTypeEnum, WishlistItem, WishlistFarmerLink, WishlistStatusEnum,
    GroupDonation, Fulfillment,
)
from routers.auth import get_current_user
from schemas import (
    WishlistItemCreate, WishlistItemUpdate, WishlistItemResponse,
    FulfillmentCreate, FulfillmentResponse,
)
from schemas.wishlist import FarmerSummary, GroupDonationSummary

router = APIRouter(prefix="/wishlist", tags=["Wishlist"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_org(user: User) -> None:
    if user.user_type != UserTypeEnum.organization:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organization accounts can manage wishlist items.",
        )


def _build_response(item: WishlistItem) -> WishlistItemResponse:
    """Convert ORM WishlistItem into a WishlistItemResponse."""
    farmers = [
        FarmerSummary(
            farmer_id=link.farmer.id,
            full_name=link.farmer.full_name,
            farm_name=link.farmer.organization_name,
            location_city=link.farmer.location_city,
        )
        for link in item.farmer_links
    ]

    gd_summary = None
    if item.group_donation:
        gd = item.group_donation
        gd_summary = GroupDonationSummary(
            id=gd.id,
            total_required=float(gd.total_required),
            amount_pledged=float(gd.amount_pledged),
            amount_remaining=float(gd.total_required) - float(gd.amount_pledged),
            donors_needed=gd.donors_needed,
            donors_count=gd.donors_count,
            donors_remaining=max(0, gd.donors_needed - gd.donors_count),
            status=gd.status.value,
        )

    return WishlistItemResponse(
        id=item.id,
        organization_id=item.organization_id,
        organization_name=item.organization.organization_name or item.organization.full_name,
        crop_name=item.crop_name,
        quantity_needed=item.quantity_needed,
        quantity_unit=item.quantity_unit,
        total_amount_required=float(item.total_amount_required),
        amount_donated=float(item.amount_donated),
        notes=item.notes,
        status=item.status,
        is_group_donation=item.is_group_donation,
        farmers=farmers,
        group_donation=gd_summary,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _load_item(db: Session, item_id: int) -> WishlistItem:
    item = (
        db.query(WishlistItem)
        .options(
            joinedload(WishlistItem.organization),
            joinedload(WishlistItem.farmer_links).joinedload(WishlistFarmerLink.farmer),
            joinedload(WishlistItem.group_donation),
        )
        .filter(WishlistItem.id == item_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Wishlist item not found.")
    return item


# ── POST /wishlist/ ───────────────────────────────────────────────────────────

@router.post(
    "/",
    response_model=WishlistItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Organization creates a wishlist item (donation opportunity)",
)
def create_wishlist_item(
    payload: WishlistItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WishlistItemResponse:
    _require_org(current_user)

    # Validate group donation requirements
    if payload.is_group_donation and not payload.donors_needed:
        raise HTTPException(
            status_code=422,
            detail="donors_needed is required when is_group_donation is True.",
        )

    # Verify all farmer IDs exist and are farmers
    farmers = (
        db.query(User)
        .filter(User.id.in_(payload.farmer_ids), User.user_type == UserTypeEnum.farmer)
        .all()
    )
    if len(farmers) != len(set(payload.farmer_ids)):
        raise HTTPException(
            status_code=422,
            detail="One or more farmer_ids are invalid or do not belong to farmer accounts.",
        )

    # Create the wishlist item
    item = WishlistItem(
        organization_id=current_user.id,
        crop_name=payload.crop_name,
        quantity_needed=payload.quantity_needed,
        quantity_unit=payload.quantity_unit,
        total_amount_required=payload.total_amount_required,
        notes=payload.notes,
        is_group_donation=payload.is_group_donation,
    )
    db.add(item)
    db.flush()  # get item.id before adding related rows

    # Link farmers
    for fid in set(payload.farmer_ids):
        db.add(WishlistFarmerLink(wishlist_item_id=item.id, farmer_id=fid))

    # Create group donation tracker if needed
    if payload.is_group_donation:
        gd = GroupDonation(
            wishlist_item_id=item.id,
            total_required=payload.total_amount_required,
            donors_needed=payload.donors_needed,
        )
        db.add(gd)

    db.commit()
    return _build_response(_load_item(db, item.id))


# ── GET /wishlist/ — marketplace feed ────────────────────────────────────────

@router.get(
    "/",
    response_model=List[WishlistItemResponse],
    summary="Browse all open wishlist items (consumer marketplace donation feed)",
)
def browse_wishlist(
    crop_name: Optional[str] = Query(None, description="Partial match on crop name"),
    org_name:  Optional[str] = Query(None, description="Partial match on org name"),
    max_amount:Optional[float]= Query(None, description="Max total amount required"),
    group_only:Optional[bool] = Query(None, description="Only show group donation opportunities"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[WishlistItemResponse]:
    q = (
        db.query(WishlistItem)
        .options(
            joinedload(WishlistItem.organization),
            joinedload(WishlistItem.farmer_links).joinedload(WishlistFarmerLink.farmer),
            joinedload(WishlistItem.group_donation),
        )
        .filter(WishlistItem.status == WishlistStatusEnum.open)
    )

    if crop_name:
        q = q.filter(WishlistItem.crop_name.ilike(f"%{crop_name}%"))
    if max_amount is not None:
        q = q.filter(WishlistItem.total_amount_required <= max_amount)
    if group_only is True:
        q = q.filter(WishlistItem.is_group_donation == True)  # noqa: E712

    items = q.order_by(WishlistItem.created_at.desc()).all()
    return [_build_response(i) for i in items]


# ── GET /wishlist/mine ────────────────────────────────────────────────────────

@router.get(
    "/mine",
    response_model=List[WishlistItemResponse],
    summary="Organization retrieves its own wishlist items",
)
def get_my_wishlist(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[WishlistItemResponse]:
    _require_org(current_user)
    items = (
        db.query(WishlistItem)
        .options(
            joinedload(WishlistItem.organization),
            joinedload(WishlistItem.farmer_links).joinedload(WishlistFarmerLink.farmer),
            joinedload(WishlistItem.group_donation),
        )
        .filter(WishlistItem.organization_id == current_user.id)
        .order_by(WishlistItem.created_at.desc())
        .all()
    )
    return [_build_response(i) for i in items]


# ── GET /wishlist/{item_id} ───────────────────────────────────────────────────

@router.get(
    "/{item_id}",
    response_model=WishlistItemResponse,
    summary="Get detail for a single wishlist item",
)
def get_wishlist_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WishlistItemResponse:
    return _build_response(_load_item(db, item_id))


# ── PATCH /wishlist/{item_id} ─────────────────────────────────────────────────

@router.patch(
    "/{item_id}",
    response_model=WishlistItemResponse,
    summary="Organization updates one of its wishlist items",
)
def update_wishlist_item(
    item_id: int,
    payload: WishlistItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WishlistItemResponse:
    _require_org(current_user)
    item = _load_item(db, item_id)

    if item.organization_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not own this wishlist item.")

    update_data = payload.model_dump(exclude_unset=True)

    # Handle farmer_ids separately
    farmer_ids = update_data.pop("farmer_ids", None)
    for field, value in update_data.items():
        setattr(item, field, value)

    if farmer_ids is not None:
        # Verify all farmer IDs exist and are farmers (same rule as create)
        farmers = (
            db.query(User)
            .filter(User.id.in_(farmer_ids), User.user_type == UserTypeEnum.farmer)
            .all()
        )
        if len(farmers) != len(set(farmer_ids)):
            raise HTTPException(
                status_code=422,
                detail="One or more farmer_ids are invalid or do not belong to farmer accounts.",
            )

        # Replace farmer links
        db.query(WishlistFarmerLink).filter(
            WishlistFarmerLink.wishlist_item_id == item_id
        ).delete(synchronize_session=False)
        for fid in set(farmer_ids):
            db.add(WishlistFarmerLink(wishlist_item_id=item_id, farmer_id=fid))

    db.commit()
    return _build_response(_load_item(db, item_id))


# ── POST /wishlist/{item_id}/fulfill ─────────────────────────────────────────

@router.post(
    "/{item_id}/fulfill",
    response_model=FulfillmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Organization marks a wishlist item fulfilled, recording pounds delivered",
)
def fulfill_wishlist_item(
    item_id: int,
    payload: FulfillmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FulfillmentResponse:
    """Records the actual delivery (the MPCA impact metric) and transitions the
    item to `fulfilled`. This is the only way to mark an item fulfilled, so
    every fulfilled item has pounds behind it."""
    _require_org(current_user)
    item = _load_item(db, item_id)

    if item.organization_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not own this wishlist item.")
    if item.status == WishlistStatusEnum.cancelled:
        raise HTTPException(status_code=409, detail="Cancelled items cannot be fulfilled.")
    if item.status == WishlistStatusEnum.fulfilled:
        raise HTTPException(status_code=409, detail="This item is already marked fulfilled.")

    if not any(link.farmer_id == payload.farmer_id for link in item.farmer_links):
        raise HTTPException(
            status_code=422,
            detail="The specified farmer is not linked to this wishlist item.",
        )

    fulfillment = Fulfillment(
        wishlist_item_id   = item.id,
        organization_id    = current_user.id,
        farmer_id          = payload.farmer_id,
        pounds_delivered   = payload.pounds_delivered,
        quantity_delivered = payload.quantity_delivered,
        quantity_unit      = payload.quantity_unit,
        notes              = payload.notes,
        delivered_at       = payload.delivered_at or datetime.utcnow(),
    )
    db.add(fulfillment)
    item.status = WishlistStatusEnum.fulfilled
    db.commit()
    db.refresh(fulfillment)
    return fulfillment


# ── DELETE /wishlist/{item_id} ────────────────────────────────────────────────

@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Organization cancels (soft-deletes) a wishlist item",
)
def cancel_wishlist_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    _require_org(current_user)
    item = _load_item(db, item_id)

    if item.organization_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not own this wishlist item.")

    item.status = WishlistStatusEnum.cancelled
    db.commit()
