"""
schemas/__init__.py — Re-exports all Pydantic request/response schemas.

This package shadows the legacy schemas.py file.
"""

from .auth import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    UserProfileResponse,
    GoogleAuthRequest,
    GoogleRegisterRequest,
    GoogleAuthResponse,
)
from .farmers import (
    CropListingCreate,
    CropListingUpdate,
    CropListingResponse,
)
from .browse import (
    CropSummary,
    FarmerListingResponse,
)
from .messaging import (
    MessageCreate,
    MessageResponse,
    ConversationSummary,
)
from .wishlist import (
    WishlistItemCreate,
    WishlistItemUpdate,
    WishlistItemResponse,
    FarmerSummary,
    GroupDonationSummary,
)
from .donations import (
    DonateRequest,
    DonationResponse,
    JoinGroupDonationRequest,
    GroupDonationParticipantResponse,
    GroupDonationResponse,
)
from .points import (
    PointsLedgerEntry,
    PointsSummaryResponse,
    TierInfo,
)
from .notifications import (
    NotificationPrefsUpdate,
    NotificationPrefsResponse,
    ProfileUpdateRequest,
    ProfileUpdateResponse,
)

__all__ = [
    # Auth
    "UserRegisterRequest", "UserLoginRequest",
    "TokenResponse", "UserProfileResponse",
    "GoogleAuthRequest", "GoogleRegisterRequest", "GoogleAuthResponse",
    # Farmers
    "CropListingCreate", "CropListingUpdate", "CropListingResponse",
    # Browse
    "CropSummary", "FarmerListingResponse",
    # Messaging
    "MessageCreate", "MessageResponse", "ConversationSummary",
    # Wishlist
    "WishlistItemCreate", "WishlistItemUpdate", "WishlistItemResponse",
    "FarmerSummary", "GroupDonationSummary",
    # Donations
    "DonateRequest", "DonationResponse",
    "JoinGroupDonationRequest", "GroupDonationParticipantResponse",
    "GroupDonationResponse",
    # Points
    "PointsLedgerEntry", "PointsSummaryResponse", "TierInfo",
    # Notifications / Profile
    "NotificationPrefsUpdate", "NotificationPrefsResponse",
    "ProfileUpdateRequest", "ProfileUpdateResponse",
]
