"""
schemas/donations.py — Pydantic schemas for Donation and GroupDonation endpoints.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from models import DonationStatusEnum, GroupDonationStatusEnum


# ── Individual donation ───────────────────────────────────────────────────────

class DonateRequest(BaseModel):
    """
    Payload sent by a consumer when clicking "Donate Now".
    The farmer_id specifies which linked farmer the consumer is paying.
    """
    wishlist_item_id: int
    farmer_id:        int
    amount:           float = Field(..., gt=0, description="Dollar amount to donate")


class DonationResponse(BaseModel):
    id:               int
    consumer_id:      int
    farmer_id:        int
    wishlist_item_id: int
    amount:           float
    status:           DonationStatusEnum
    points_earned:    int = 0
    created_at:       datetime

    model_config = {"from_attributes": True}


class CheckoutResponse(BaseModel):
    """
    Returned when a donation (individual or group) is initiated: the frontend
    redirects the browser to `checkout_url`. The donation is `pending` until
    the Stripe webhook confirms it — poll GET /donations/{donation_id}.
    """
    donation_id:  int
    checkout_url: str
    status:       DonationStatusEnum = DonationStatusEnum.pending


# ── Group donation join ───────────────────────────────────────────────────────

class JoinGroupDonationRequest(BaseModel):
    """
    Payload sent by a consumer when clicking "Join Group Donation".
    amount is the per-person pledge for this group donation.
    """
    group_donation_id: int
    amount:            float = Field(..., gt=0)


class GroupDonationParticipantResponse(BaseModel):
    id:                int
    group_donation_id: int
    consumer_id:       int
    amount_pledged:    float
    joined_at:         datetime

    model_config = {"from_attributes": True}


class GroupDonationResponse(BaseModel):
    id:               int
    wishlist_item_id: int
    total_required:   float
    amount_pledged:   float
    amount_remaining: float
    donors_needed:    int
    donors_count:     int
    donors_remaining: int
    status:           GroupDonationStatusEnum
    created_at:       datetime
    updated_at:       datetime

    model_config = {"from_attributes": True}
