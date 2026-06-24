"""
schemas.py — Pydantic models for request / response validation
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, field_validator
from models import FulfillmentStatusEnum, UserTypeEnum

# ────────────────────────────────────────────────────────────────────────────
# Allowed predefined crops
# ────────────────────────────────────────────────────────────────────────────
PREDEFINED_CROPS = {"lettuce", "cucumbers", "tomatoes"}


# ═══════════════════════════════════════════════════════════════════════════
# Auth / User schemas
# ═══════════════════════════════════════════════════════════════════════════

class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str
    user_type: UserTypeEnum

    # Profile fields
    full_name: Optional[str]         = None
    organization_name: Optional[str] = None
    address: Optional[str]           = None
    city: Optional[str]              = None
    state: Optional[str]             = None
    zip_code: Optional[str]          = None
    phone: Optional[str]             = None

    model_config = {"from_attributes": True}


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_type: UserTypeEnum
    user_id: int
    email: str


class UserProfileResponse(BaseModel):
    id: int
    email: str
    user_type: UserTypeEnum
    full_name: Optional[str]
    organization_name: Optional[str]
    address: Optional[str]
    city: Optional[str]
    state: Optional[str]
    zip_code: Optional[str]
    phone: Optional[str]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════════════════
# Crop request schemas
# ═══════════════════════════════════════════════════════════════════════════

class CropRequestCreate(BaseModel):
    """Payload sent by an organization when submitting a crop request."""
    crops_low_in_stock: List[str]       # must be from PREDEFINED_CROPS
    nice_to_have_crops: Optional[str]   = None

    @field_validator("crops_low_in_stock")
    @classmethod
    def validate_crops(cls, crops: List[str]) -> List[str]:
        invalid = set(crops) - PREDEFINED_CROPS
        if invalid:
            raise ValueError(
                f"Invalid crops: {invalid}. "
                f"Allowed values: {PREDEFINED_CROPS}"
            )
        return [c.lower().strip() for c in crops]


class CropRequestResponse(BaseModel):
    id: int
    organization_id: int
    crops_low_in_stock: str          # stored as CSV in DB
    nice_to_have_crops: Optional[str]
    fulfillment_status: FulfillmentStatusEnum
    created_at: datetime
    updated_at: datetime

    # Org details (populated via join)
    organization_name: Optional[str] = None
    city: Optional[str]              = None
    state: Optional[str]             = None

    model_config = {"from_attributes": True}


class CropRequestStatusUpdate(BaseModel):
    """Allows updating the fulfillment status (admin / future donor use)."""
    fulfillment_status: FulfillmentStatusEnum


# ═══════════════════════════════════════════════════════════════════════════
# Future-proof: Donor notification stub
# ═══════════════════════════════════════════════════════════════════════════

class DonorNotificationRequest(BaseModel):
    """Placeholder schema for the donor notification system."""
    donor_id: int
    message: str
    crop_request_id: Optional[int] = None
