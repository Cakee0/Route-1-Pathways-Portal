"""
models/__init__.py — Re-exports all ORM models so the rest of the codebase
can simply write `from models import User, FarmerCropInventory, Message`.

This package shadows the legacy models.py file (Python packages take precedence
over same-named modules on sys.path).
"""

from .user import User, UserTypeEnum, OrgSubtypeEnum
from .crop_inventory import FarmerCropInventory
from .messaging import Message, make_conversation_id
from .wishlist import WishlistItem, WishlistFarmerLink, WishlistStatusEnum
from .fulfillment import Fulfillment
from .donation import (
    Donation, DonationStatusEnum,
    GroupDonation, GroupDonationStatusEnum,
    GroupDonationParticipant,
)
from .points import PointsLedger, calculate_points, TIER_THRESHOLDS
from .notification_prefs import NotificationPreferences
from .order import CropOrder, OrderStatusEnum

__all__ = [
    # Core auth
    "User",
    "UserTypeEnum",
    "OrgSubtypeEnum",
    # Inventory
    "FarmerCropInventory",
    # Messaging
    "Message",
    "make_conversation_id",
    # Wishlist
    "WishlistItem",
    "WishlistFarmerLink",
    "WishlistStatusEnum",
    "Fulfillment",
    # Donations
    "Donation",
    "DonationStatusEnum",
    "GroupDonation",
    "GroupDonationStatusEnum",
    "GroupDonationParticipant",
    # Points
    "PointsLedger",
    "calculate_points",
    "TIER_THRESHOLDS",
    # Notifications
    "NotificationPreferences",
    # Direct crop orders
    "CropOrder",
    "OrderStatusEnum",
]
