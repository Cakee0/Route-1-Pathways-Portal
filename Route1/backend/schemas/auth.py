"""
schemas/auth.py — Pydantic request/response schemas for authentication endpoints.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, model_validator

from models import OrgSubtypeEnum, UserTypeEnum


# ── Registration ─────────────────────────────────────────────────────────────

class UserRegisterRequest(BaseModel):
    email:    EmailStr
    # 72-char cap matches bcrypt's 72-byte input limit (see utils/security.py).
    password: str = Field(
        ..., min_length=8, max_length=72,
        description="8–72 characters",
    )
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
        if self.user_type == UserTypeEnum.farmer and (
            not (self.location_city or "").strip()
            or not (self.location_region or "").strip()
        ):
            raise ValueError(
                "Farmers must provide a Minnesota city and region — "
                "buyers use it to find listings near them."
            )
        return self

    model_config = {"from_attributes": True}


# ── Login ─────────────────────────────────────────────────────────────────────

class UserLoginRequest(BaseModel):
    email:    EmailStr
    password: str


# ── Google sign-in ────────────────────────────────────────────────────────────

class GoogleAuthRequest(BaseModel):
    """Google ID token (JWT) returned by Google Identity Services on the client."""
    credential: str


class GoogleRegisterRequest(BaseModel):
    """Finish a Google sign-up by choosing an account type.

    The same Google `credential` is re-verified server-side, so the role (and,
    for farmers, the required location) is all the client contributes here.
    """
    credential:  str
    user_type:   UserTypeEnum
    org_subtype: Optional[OrgSubtypeEnum] = None

    # Farmers must provide these; ignored-if-empty for other roles
    location_city:   Optional[str] = None
    location_region: Optional[str] = None

    @model_validator(mode="after")
    def org_subtype_required_for_organization(self) -> "GoogleRegisterRequest":
        if self.user_type == UserTypeEnum.organization and self.org_subtype is None:
            raise ValueError(
                "org_subtype is required for organization accounts. "
                "Choose: restaurant, grocery_store, or food_shelf."
            )
        if self.user_type == UserTypeEnum.farmer and (
            not (self.location_city or "").strip()
            or not (self.location_region or "").strip()
        ):
            raise ValueError(
                "Farmers must provide a Minnesota city and region — "
                "buyers use it to find listings near them."
            )
        return self


class GoogleAuthResponse(BaseModel):
    """Result of POST /auth/google.

    - needs_registration=True  → brand-new Google user; the client must collect a
      role and call POST /auth/google/complete. `access_token` is null.
    - needs_registration=False → known (or auto-linked) user; a normal token is
      returned, same shape as TokenResponse.
    """
    needs_registration: bool
    email:      Optional[str] = None
    full_name:  Optional[str] = None

    access_token: Optional[str] = None
    token_type:   str = "bearer"
    user_type:    Optional[UserTypeEnum] = None
    org_subtype:  Optional[OrgSubtypeEnum] = None
    user_id:      Optional[int] = None


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

    # Carried on the login response so the client can render the user's own
    # avatar in the header, and know whether to nudge them to fill their
    # profile in, without a second request on every page load.
    avatar_url:        Optional[str] = None
    tagline:           Optional[str] = None
    bio:               Optional[str] = None
    year_started:      Optional[int] = None

    model_config = {"from_attributes": True}
