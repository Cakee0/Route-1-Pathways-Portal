"""
routers/donations.py — Donation and Group Donation endpoints (Stripe-backed).

Money path (see OPERATIONS.local.md §12 and utils/payments.py):
  1. Consumer initiates a donation → a `pending` Donation row is created and a
     Stripe Checkout Session is opened. The endpoint returns `checkout_url`;
     the frontend redirects the browser there.
  2. Consumer pays on Stripe's hosted page.
  3. Stripe calls POST /webhooks/stripe → `confirm_paid_donation()` (below)
     flips the donation to `confirmed`, updates funding progress, and awards
     points. The signed webhook — never the browser redirect — is the source
     of truth, so nothing here confirms a donation or awards points on its own.

Individual donations and group donations share the same machinery: a group join
charges the donor immediately (charge-at-join) and funds the wishlist item
incrementally. There is no all-or-nothing escrow and no refund-on-failure path.

Endpoints:
  POST /donations/               — start an individual donation  → CheckoutResponse
  POST /donations/group/join     — join a group donation         → CheckoutResponse
  GET  /donations/{donation_id}  — poll a single donation's status (owner only)
  GET  /donations/group/{gd_id}  — fetch group donation status
  GET  /donations/mine           — consumer's donation history
"""

import logging
from datetime import datetime, timedelta
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
    DonateRequest, DonationResponse, CheckoutResponse,
    JoinGroupDonationRequest, GroupDonationParticipantResponse, GroupDonationResponse,
)
from utils import payments
from utils.notify import notify_group_progress

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/donations", tags=["Donations"])


# ── Guards ────────────────────────────────────────────────────────────────────

def _require_consumer(user: User) -> None:
    if user.user_type != UserTypeEnum.consumer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only consumer accounts can make contributions.",
        )


def _require_payments_configured() -> None:
    if not payments.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payments are not available yet. Please try again later.",
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
            description=f"Contributed ${donation.amount:.2f} — {pts} pts awarded",
        )
        db.add(entry)
    return pts


# ── POST /donations/ — start an individual donation ───────────────────────────

@router.post(
    "/",
    response_model=CheckoutResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start an individual contribution (returns a Stripe Checkout URL)",
)
def donate(
    payload: DonateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CheckoutResponse:
    _require_consumer(current_user)
    _require_payments_configured()

    item = (
        db.query(WishlistItem)
        .filter(WishlistItem.id == payload.wishlist_item_id)
        .first()
    )
    if not item or item.status != WishlistStatusEnum.open:
        raise HTTPException(status_code=404, detail="Wishlist item not found or not accepting contributions.")

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

    # Create the donation as PENDING. It is confirmed only by the Stripe webhook.
    donation = Donation(
        consumer_id=current_user.id,
        farmer_id=payload.farmer_id,
        wishlist_item_id=payload.wishlist_item_id,
        amount=payload.amount,
        currency="usd",
        status=DonationStatusEnum.pending,
    )
    db.add(donation)
    db.flush()  # assign donation.id without committing

    org_name = item.organization.organization_name or item.organization.full_name or "an organization"
    checkout_url = _open_checkout(
        db, donation,
        crop_name=item.crop_name, org_name=org_name,
        kind="individual", customer_email=current_user.email,
    )

    return CheckoutResponse(donation_id=donation.id, checkout_url=checkout_url)


# ── POST /donations/group/join — charge-at-join ───────────────────────────────

@router.post(
    "/group/join",
    response_model=CheckoutResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Join a group donation (charges immediately; returns a Checkout URL)",
)
def join_group_donation(
    payload: JoinGroupDonationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CheckoutResponse:
    _require_consumer(current_user)
    _require_payments_configured()

    gd = (
        db.query(GroupDonation)
        .filter(GroupDonation.id == payload.group_donation_id)
        .first()
    )
    if not gd or gd.status != GroupDonationStatusEnum.open:
        raise HTTPException(status_code=404, detail="Group donation not found or no longer accepting participants.")

    item = gd.wishlist_item
    if not item or not item.farmer_links:
        raise HTTPException(
            status_code=409,
            detail="This group donation has no linked farmer; the organization must fix it before it can be funded.",
        )
    farmer_id = item.farmer_links[0].farmer_id

    # One pledge per consumer per group. A CONFIRMED prior pledge blocks a
    # second; an abandoned PENDING attempt is discarded so the consumer can
    # retry with a fresh Checkout Session.
    existing = (
        db.query(GroupDonationParticipant)
        .filter(
            GroupDonationParticipant.group_donation_id == gd.id,
            GroupDonationParticipant.consumer_id == current_user.id,
        )
        .first()
    )
    if existing:
        prior = existing.donation
        if prior and prior.status == DonationStatusEnum.confirmed:
            raise HTTPException(status_code=409, detail="You have already contributed to this group donation.")
        # Discard the stale attempt and its unpaid donation row. `expired`
        # counts as stale too — it's a pending attempt we already swept.
        if prior and prior.status in (DonationStatusEnum.pending, DonationStatusEnum.expired):
            db.delete(prior)
        db.delete(existing)
        db.flush()

    donation = Donation(
        consumer_id=current_user.id,
        farmer_id=farmer_id,
        wishlist_item_id=item.id,
        amount=payload.amount,
        currency="usd",
        status=DonationStatusEnum.pending,
        group_donation_id=gd.id,
    )
    db.add(donation)
    db.flush()

    participant = GroupDonationParticipant(
        group_donation_id=gd.id,
        consumer_id=current_user.id,
        donation_id=donation.id,
        amount_pledged=payload.amount,
    )
    db.add(participant)
    try:
        db.flush()
    except IntegrityError:
        # uq_gdp_group_consumer — a concurrent join from the same consumer won
        # the race past the check above.
        db.rollback()
        raise HTTPException(status_code=409, detail="You have already contributed to this group donation.")

    org_name = item.organization.organization_name or item.organization.full_name or "an organization"
    checkout_url = _open_checkout(
        db, donation,
        crop_name=item.crop_name, org_name=org_name,
        kind="group", customer_email=current_user.email,
    )

    return CheckoutResponse(donation_id=donation.id, checkout_url=checkout_url)


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
    # Safety net for abandoned checkouts whose expiry event never arrived, so
    # the history a consumer reads is never stuck showing a dead "pending".
    expire_stale_pending_donations(db)
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


# ── GET /donations/{donation_id} — poll status (owner only) ───────────────────
# Declared AFTER /mine and /group/{gd_id}: a bare "/{donation_id}" matches any
# single non-slash segment, so placing it earlier would shadow "/mine" (FastAPI
# would try to parse "mine" as an int and 422 instead of routing to it).

@router.get(
    "/{donation_id}",
    response_model=DonationResponse,
    summary="Fetch one donation's current status (for the post-checkout page)",
)
def get_donation(
    donation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DonationResponse:
    donation = (
        db.query(Donation)
        .options(joinedload(Donation.points_entry))
        .filter(Donation.id == donation_id)
        .first()
    )
    # 404 (not 403) for someone else's donation — don't reveal it exists.
    if not donation or donation.consumer_id != current_user.id:
        raise HTTPException(status_code=404, detail="Donation not found.")
    return DonationResponse(
        id=donation.id,
        consumer_id=donation.consumer_id,
        farmer_id=donation.farmer_id,
        wishlist_item_id=donation.wishlist_item_id,
        amount=float(donation.amount),
        status=donation.status,
        points_earned=donation.points_entry.points if donation.points_entry else 0,
        created_at=donation.created_at,
    )


# ── Internal: open a Checkout Session for a pending donation ───────────────────

def _open_checkout(
    db: Session,
    donation: Donation,
    *,
    crop_name: str,
    org_name: str,
    kind: str,
    customer_email: str,
) -> str:
    """
    Create a Stripe Checkout Session for a freshly-flushed pending donation,
    persist its id, and return the redirect URL. Rolls back the pending
    donation (and anything else in the transaction) if Stripe errors, so no
    orphaned rows are left behind.
    """
    try:
        session = payments.create_checkout_session(
            donation_id=donation.id,
            amount=float(donation.amount),
            currency=donation.currency,
            crop_name=crop_name,
            org_name=org_name,
            kind=kind,
            customer_email=customer_email,
        )
        donation.stripe_session_id = session.id
        db.commit()
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception("Stripe Checkout Session creation failed for a %s donation", kind)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not start the payment. Please try again.",
        )

    if not session.url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Payment provider did not return a checkout URL.",
        )
    return session.url


# ── Confirmation (called ONLY by the Stripe webhook) ──────────────────────────

# ── Abandoned checkouts ───────────────────────────────────────────────────────
#
# Opening Stripe Checkout and closing the tab is a normal thing to do, and it
# leaves a `pending` donation behind. Two mechanisms retire those:
#
#   1. Stripe's `checkout.session.expired` event (routers/webhooks.py) — the
#      precise one, fired ~24h after the session was created.
#   2. The sweep below, as a safety net for rows whose event never arrived
#      (webhook downtime, or donations predating this feature).
#
# Neither touches money or progress counters: a pending donation has never
# incremented a wishlist total, a group's pledged amount, or anyone's points —
# those only move in confirm_paid_donation.

# Stripe sessions last 24h; leave a margin so this never races the real event.
_STALE_AFTER = timedelta(hours=26)


def expire_donation(db: Session, donation_id: int) -> bool:
    """Retire one abandoned donation. Returns True if it changed anything."""
    donation = (
        db.query(Donation)
        .filter(Donation.id == donation_id)
        .with_for_update()
        .first()
    )
    if not donation or donation.status != DonationStatusEnum.pending:
        return False   # already confirmed, refunded, or expired — leave it alone

    donation.status = DonationStatusEnum.expired

    # A group contribution also holds a participant slot. Release it, or the
    # consumer can never re-join the group they abandoned.
    if donation.group_donation_id:
        db.query(GroupDonationParticipant).filter(
            GroupDonationParticipant.donation_id == donation.id
        ).delete(synchronize_session=False)

    db.commit()
    logger.info("Donation %s expired (checkout abandoned).", donation_id)
    return True


def expire_stale_pending_donations(db: Session) -> int:
    """
    Safety net: retire pending donations older than the Stripe session lifetime.
    Cheap enough to call on a read path — it's one indexed UPDATE, and matches
    nothing on the overwhelming majority of calls.
    """
    cutoff = datetime.utcnow() - _STALE_AFTER
    stale = (
        db.query(Donation)
        .filter(Donation.status == DonationStatusEnum.pending,
                Donation.created_at < cutoff)
        .all()
    )
    count = 0
    for d in stale:
        if expire_donation(db, d.id):
            count += 1
    if count:
        logger.info("Swept %d stale pending donation(s).", count)
    return count


def confirm_paid_donation(db: Session, donation_id: int, payment_intent_id: str | None) -> None:
    """
    Confirm a donation that Stripe reports as paid. Idempotent: safe to call
    again for the same donation (Stripe retries webhooks), because a donation
    already `confirmed`/`refunded` returns immediately, and the FOR UPDATE lock
    serialises concurrent deliveries on the donation row.

    Effects on first confirmation:
      * status → confirmed, PaymentIntent recorded
      * wishlist item amount_donated increased (→ funded at the threshold)
      * group donation amount_pledged / donors_count increased (if applicable)
      * reward points awarded (also guarded by uq_pl_donation)
    """
    donation = (
        db.query(Donation)
        .filter(Donation.id == donation_id)
        .with_for_update()
        .first()
    )
    if not donation:
        logger.warning("Webhook confirm: donation_id=%s not found — ignoring.", donation_id)
        return
    # `expired` is accepted here on purpose: if money somehow lands after we've
    # swept a donation as abandoned (a delayed payment method clearing, say),
    # the payment must win over our own housekeeping. Never drop a real payment
    # because of a timer.
    if donation.status not in (DonationStatusEnum.pending, DonationStatusEnum.expired):
        # Already confirmed (webhook retry) or refunded — do nothing.
        logger.info("Webhook confirm: donation_id=%s already %s — no-op.", donation_id, donation.status)
        return
    if donation.status == DonationStatusEnum.expired:
        logger.info("Webhook confirm: donation_id=%s was expired but paid — confirming.", donation_id)

    donation.status = DonationStatusEnum.confirmed
    if payment_intent_id:
        donation.stripe_payment_intent_id = payment_intent_id
        donation.payment_reference = payment_intent_id

    # Update wishlist funding progress (locked to avoid lost updates).
    item = (
        db.query(WishlistItem)
        .filter(WishlistItem.id == donation.wishlist_item_id)
        .with_for_update()
        .first()
    )
    if item:
        item.amount_donated = float(item.amount_donated) + float(donation.amount)
        if (
            float(item.amount_donated) >= float(item.total_amount_required)
            and item.status == WishlistStatusEnum.open
        ):
            item.status = WishlistStatusEnum.funded

    # Update group progress if this is a group contribution (locked).
    gd = None
    if donation.group_donation_id:
        gd = (
            db.query(GroupDonation)
            .filter(GroupDonation.id == donation.group_donation_id)
            .with_for_update()
            .first()
        )
        if gd:
            gd.amount_pledged = float(gd.amount_pledged) + float(donation.amount)
            gd.donors_count = gd.donors_count + 1

            # If this donation had been swept as abandoned, its participant row
            # was released. Money arriving afterwards must restore the donor's
            # place, or the group would count the amount but lose the person.
            has_slot = (
                db.query(GroupDonationParticipant)
                .filter(GroupDonationParticipant.donation_id == donation.id)
                .first()
            )
            if not has_slot:
                db.add(GroupDonationParticipant(
                    group_donation_id=gd.id,
                    consumer_id=donation.consumer_id,
                    donation_id=donation.id,
                    amount_pledged=donation.amount,
                ))
            if (
                float(gd.amount_pledged) >= float(gd.total_required)
                and gd.status == GroupDonationStatusEnum.open
            ):
                gd.status = GroupDonationStatusEnum.funded

    _award_points(db, donation)

    try:
        db.commit()
    except IntegrityError:
        # uq_pl_donation — a concurrent confirm already awarded points for this
        # donation. Roll back and leave the winning transaction's result intact.
        db.rollback()
        logger.info("Webhook confirm: donation_id=%s already awarded — no-op.", donation_id)
        return

    # Group-progress notifications (e.g. "one more donor needed") fire on the
    # confirmed donor count, and must never break the money path.
    if gd is not None:
        try:
            notify_group_progress(db, gd)
        except Exception:
            logger.exception("group-donation notification failure")
