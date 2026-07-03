"""
routers/donations.py — Donation and Group Donation endpoints.

Individual Donation flow:
  POST /donations/               — consumer donates to a wishlist item

Group Donation flow:
  POST /donations/group/join     — consumer joins an existing group donation
  GET  /donations/group/{gd_id}  — fetch group donation status
  GET  /donations/mine           — consumer's donation history

Notification triggers (utils/notify.py) alert opted-in consumers by email:
group-progress notifications fire here on join; new-opportunity
notifications fire on wishlist item creation (routers/wishlist.py).
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import (
    User, UserTypeEnum,
    WishlistItem, WishlistStatusEnum,
    Donation, DonationStatusEnum,
    GroupDonation, GroupDonationStatusEnum, GroupDonationParticipant,
    PointsLedger, calculate_points,
)
from routers.auth import get_current_user
from schemas import (
    DonateRequest, DonationResponse,
    JoinGroupDonationRequest, GroupDonationParticipantResponse, GroupDonationResponse,
)
from utils.notify import notify_group_progress

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/donations", tags=["Donations"])


# ── Guards ────────────────────────────────────────────────────────────────────

def _require_consumer(user: User) -> None:
    if user.user_type != UserTypeEnum.consumer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only consumer accounts can make donations.",
        )


# ── Points helper ─────────────────────────────────────────────────────────────

def _award_points(db: Session, donation: Donation) -> int:
    """Create a PointsLedger entry for a confirmed donation. Returns points awarded."""
    pts = calculate_points(float(donation.amount))
    if pts > 0:
        entry = PointsLedger(
            consumer_id=donation.consumer_id,
            donation_id=donation.id,
            points=pts,
            amount_basis=donation.amount,
            description=f"Donated ${donation.amount:.2f} — {pts} pts awarded",
        )
        db.add(entry)
    return pts


# ── POST /donations/ — individual donation ────────────────────────────────────

@router.post(
    "/",
    response_model=DonationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Consumer donates to a wishlist item (individual donation)",
)
def donate(
    payload: DonateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DonationResponse:
    _require_consumer(current_user)

    # Validate wishlist item — locked so two concurrent donations can't both
    # read the same amount_donated and lose one update (audit A6)
    item = (
        db.query(WishlistItem)
        .filter(WishlistItem.id == payload.wishlist_item_id)
        .with_for_update()
        .first()
    )
    if not item or item.status != WishlistStatusEnum.open:
        raise HTTPException(status_code=404, detail="Wishlist item not found or not accepting donations.")

    if item.is_group_donation:
        raise HTTPException(
            status_code=422,
            detail="This is a group donation. Use POST /donations/group/join instead.",
        )

    # Validate farmer is linked to this wishlist item
    linked = any(link.farmer_id == payload.farmer_id for link in item.farmer_links)
    if not linked:
        raise HTTPException(
            status_code=422,
            detail="The specified farmer is not linked to this wishlist item.",
        )

    # Create the donation (confirmed immediately for now; integrate payment gateway later)
    donation = Donation(
        consumer_id=current_user.id,
        farmer_id=payload.farmer_id,
        wishlist_item_id=payload.wishlist_item_id,
        amount=payload.amount,
        status=DonationStatusEnum.confirmed,
    )
    db.add(donation)
    db.flush()

    # Update wishlist amount_donated
    item.amount_donated = float(item.amount_donated) + payload.amount
    if float(item.amount_donated) >= float(item.total_amount_required):
        item.status = WishlistStatusEnum.funded

    # Award points
    pts = _award_points(db, donation)

    db.commit()
    db.refresh(donation)

    return DonationResponse(
        id=donation.id,
        consumer_id=donation.consumer_id,
        farmer_id=donation.farmer_id,
        wishlist_item_id=donation.wishlist_item_id,
        amount=float(donation.amount),
        status=donation.status,
        points_earned=pts,
        created_at=donation.created_at,
    )


# ── POST /donations/group/join ────────────────────────────────────────────────

@router.post(
    "/group/join",
    response_model=GroupDonationParticipantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Consumer joins a group donation",
)
def join_group_donation(
    payload: JoinGroupDonationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GroupDonationParticipantResponse:
    _require_consumer(current_user)

    # Locked so concurrent joins can't double-count pledges or double-fire the
    # funded transition (audit A6). No joinedload here — FOR UPDATE must lock
    # only the group_donations row; related rows lazy-load as needed.
    gd = (
        db.query(GroupDonation)
        .filter(GroupDonation.id == payload.group_donation_id)
        .with_for_update()
        .first()
    )
    if not gd or gd.status != GroupDonationStatusEnum.open:
        raise HTTPException(status_code=404, detail="Group donation not found or no longer accepting participants.")

    # Prevent duplicate participation
    existing = (
        db.query(GroupDonationParticipant)
        .filter(
            GroupDonationParticipant.group_donation_id == gd.id,
            GroupDonationParticipant.consumer_id == current_user.id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="You have already joined this group donation.")

    # Add participant
    participant = GroupDonationParticipant(
        group_donation_id=gd.id,
        consumer_id=current_user.id,
        amount_pledged=payload.amount,
    )
    db.add(participant)

    # Update group totals
    gd.amount_pledged = float(gd.amount_pledged) + payload.amount
    gd.donors_count   = gd.donors_count + 1

    # Check if group is now fully funded
    if float(gd.amount_pledged) >= float(gd.total_required):
        gd.status = GroupDonationStatusEnum.funded
        gd.wishlist_item.status = WishlistStatusEnum.funded
        # Confirm all participant donations & award points
        _confirm_group_donations(db, gd)

    try:
        db.commit()
    except IntegrityError:
        # uq_gdp_group_consumer — a concurrent request from the same consumer
        # won the race past the check above
        db.rollback()
        raise HTTPException(status_code=409, detail="You have already joined this group donation.")
    db.refresh(participant)

    # Fire group-donation notifications (e.g. "one donor away") — must never
    # break the response
    try:
        notify_group_progress(db, gd)
    except Exception:
        logger.exception("group-donation notification failure")

    return GroupDonationParticipantResponse(
        id=participant.id,
        group_donation_id=participant.group_donation_id,
        consumer_id=participant.consumer_id,
        amount_pledged=float(participant.amount_pledged),
        joined_at=participant.joined_at,
    )


# ── GET /donations/group/{gd_id} ──────────────────────────────────────────────

@router.get(
    "/group/{gd_id}",
    response_model=GroupDonationResponse,
    summary="Fetch current status of a group donation",
)
def get_group_donation(
    gd_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GroupDonationResponse:
    gd = db.query(GroupDonation).filter(GroupDonation.id == gd_id).first()
    if not gd:
        raise HTTPException(status_code=404, detail="Group donation not found.")
    return GroupDonationResponse(
        id=gd.id,
        wishlist_item_id=gd.wishlist_item_id,
        total_required=float(gd.total_required),
        amount_pledged=float(gd.amount_pledged),
        amount_remaining=max(0, float(gd.total_required) - float(gd.amount_pledged)),
        donors_needed=gd.donors_needed,
        donors_count=gd.donors_count,
        donors_remaining=max(0, gd.donors_needed - gd.donors_count),
        status=gd.status,
        created_at=gd.created_at,
        updated_at=gd.updated_at,
    )


# ── GET /donations/mine ───────────────────────────────────────────────────────

@router.get(
    "/mine",
    response_model=List[DonationResponse],
    summary="Consumer retrieves their donation history",
)
def my_donations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[DonationResponse]:
    _require_consumer(current_user)
    donations = (
        db.query(Donation)
        .options(joinedload(Donation.points_entry))
        .filter(Donation.consumer_id == current_user.id)
        .order_by(Donation.created_at.desc())
        .all()
    )
    return [
        DonationResponse(
            id=d.id,
            consumer_id=d.consumer_id,
            farmer_id=d.farmer_id,
            wishlist_item_id=d.wishlist_item_id,
            amount=float(d.amount),
            status=d.status,
            points_earned=d.points_entry.points if d.points_entry else 0,
            created_at=d.created_at,
        )
        for d in donations
    ]


# ── Internal helpers ──────────────────────────────────────────────────────────

def _confirm_group_donations(db: Session, gd: GroupDonation) -> None:
    """
    When a group donation reaches its goal, create confirmed Donation rows
    for each participant and award them points.
    """
    item = gd.wishlist_item
    if not item.farmer_links:
        # donations.farmer_id is NOT NULL — fail the request cleanly here,
        # before any money state is committed, instead of 500ing at commit
        raise HTTPException(
            status_code=409,
            detail="This wishlist item has no linked farmer; the organization must fix it before the group can be funded.",
        )
    # Pick primary farmer (first linked)
    farmer_id = item.farmer_links[0].farmer_id

    for participant in gd.participants:
        if participant.donation_id:
            continue  # already confirmed

        donation = Donation(
            consumer_id=participant.consumer_id,
            farmer_id=farmer_id,
            wishlist_item_id=item.id,
            amount=participant.amount_pledged,
            status=DonationStatusEnum.confirmed,
            group_donation_id=gd.id,
        )
        db.add(donation)
        db.flush()

        participant.donation_id = donation.id
        _award_points(db, donation)
