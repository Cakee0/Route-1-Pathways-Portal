"""
routers/donors.py — Future-proof stub for wealthy donor features.

Endpoints defined here will be expanded in Phase 2 to support:
  - Donor account management
  - Push / email notifications when crop needs are critical
  - Donation pledge and processing flow
  - Farmer-to-donor matchmaking
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models import User, UserTypeEnum
from routers.auth import get_current_user
from schemas import DonorNotificationRequest

router = APIRouter(prefix="/donors", tags=["Donors (Future Expansion)"])


def _require_donor(user: User):
    if user.user_type != UserTypeEnum.donor:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only donor accounts can access this endpoint.",
        )


# ── GET /donors/me ────────────────────────────────────────────────────────────
@router.get(
    "/me",
    summary="[STUB] Return the authenticated donor's profile",
)
def donor_profile(current_user: User = Depends(get_current_user)):
    _require_donor(current_user)
    return {
        "id":        current_user.id,
        "email":     current_user.email,
        "full_name": current_user.full_name,
        "message":   "Donor profile endpoint — full donor features coming in Phase 2.",
    }


# ── POST /donors/notify ───────────────────────────────────────────────────────
@router.post(
    "/notify",
    status_code=status.HTTP_202_ACCEPTED,
    summary="[STUB] Send donor a notification about a crop request",
)
def notify_donor(
    payload: DonorNotificationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Phase 2 implementation will:
    1. Look up the donor by payload.donor_id.
    2. Send an email / push notification via AWS SES or SNS.
    3. Log the notification in a `notifications` table.
    """
    return {
        "status":  "accepted",
        "message": (
            f"Notification queued for donor {payload.donor_id}. "
            "Full notification delivery will be implemented in Phase 2."
        ),
    }


# ── POST /donors/donate ───────────────────────────────────────────────────────
@router.post(
    "/donate",
    status_code=status.HTTP_202_ACCEPTED,
    summary="[STUB] Donor pledges a monetary donation to a farmer",
)
def process_donation(current_user: User = Depends(get_current_user)):
    """
    Phase 2 implementation will integrate a payment gateway
    (e.g., Stripe) to process donations from wealthy donors to farmers.
    """
    _require_donor(current_user)
    return {
        "status":  "stub",
        "message": "Donation processing will be implemented in Phase 2.",
    }
