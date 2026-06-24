"""
schemas/auth.py — Pydantic request/response schemas for authentication endpoints.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator, model_validator

from models import OrgSubtypeEnum, UserTypeEnum


# ── Registration ─────────────────────────────────────────────────────────────

class UserRegisterRequest(BaseModel):
    email:    EmailStr
    password: str
    user_type: UserTypeEnum

    # Organizations must specify a sub-type
    org_subtype: Optional[OrgSubtypeEnum] = None

    # Shared profile fields
    full_name:         Optional[str] = None
    organization_name: Optional[str] = None   # farm name for farmers, org name for orgs
    location_city:     Optional[str] = None   # Minnesota city
    location_region:   Optional[str] = None   # Minnesota region
    phone:             Optional[str] = None

    @model_validator(mode="after")
    def org_subtype_required_for_organization(self) -> "UserRegisterRequest":
        if self.user_type == UserTypeEnum.organization and self.org_subtype is None:
            raise ValueError(
                "org_subtype is required for organization accounts. "
                "Choose: restaurant, grocery_store, or food_shelf."
            )
        if self.user_type == UserTypeEnum.consumer:
            self.organization_name = None
        return self

    model_config = {"from_attributes": True}


# ── Login ─────────────────────────────────────────────────────────────────────

class UserLoginRequest(BaseModel):
    email:    EmailStr
    password: str


# ── Token response ────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user_type:    UserTypeEnum
    org_subtype:  Optional[OrgSubtypeEnum] = None
    user_id:      int
    email:        str


# ── Profile response ──────────────────────────────────────────────────────────

class UserProfileResponse(BaseModel):
    id:                int
    email:             str
    user_type:         UserTypeEnum
    org_subtype:       Optional[OrgSubtypeEnum]
    full_name:         Optional[str]
    organization_name: Optional[str]
    location_city:     Optional[str]
    location_region:   Optional[str]
    phone:             Optional[str]
    is_active:         bool
    created_at:        datetime

    model_config = {"from_attributes": True}
