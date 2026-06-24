"""
routers/profiles.py — Profile settings endpoints for all user types.

All three user roles (farmer, organization, consumer) can update their
own profile information via PATCH /profiles/me.

Consumer-only: also update notification preferences at
  GET  /profiles/me/notifications
  PATCH /profiles/me/notifications
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models import User, NotificationPreferences
from routers.auth import get_current_user
from schemas import (
    ProfileUpdateRequest,
    ProfileUpdateResponse,
    NotificationPrefsUpdate,
    NotificationPrefsResponse,
)

router = APIRouter(prefix="/profiles", tags=["Profiles"])


# ── PATCH /profiles/me ────────────────────────────────────────────────────────

@router.patch(
    "/me",
    response_model=ProfileUpdateResponse,
    summary="Update current user's profile (all roles)",
)
def update_profile(
    payload: ProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Partial update — only the fields included in the request body are changed.
    Works for farmers, organizations, and consumers.
    """
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(current_user, field, value)

    db.commit()
    db.refresh(current_user)
    return current_user


# ── GET /profiles/me ──────────────────────────────────────────────────────────

@router.get(
    "/me",
    response_model=ProfileUpdateResponse,
    summary="Get current user's profile",
)
def get_profile(
    current_user: User = Depends(get_current_user),
) -> User:
    return current_user


# ── GET /profiles/me/notifications ───────────────────────────────────────────

@router.get(
    "/me/notifications",
    response_model=NotificationPrefsResponse,
    summary="Get notification preferences (consumer only)",
)
def get_notification_prefs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationPreferences:
    _require_consumer(current_user)
    prefs = _get_or_create_prefs(db, current_user.id)
    return prefs


# ── PATCH /profiles/me/notifications ─────────────────────────────────────────

@router.patch(
    "/me/notifications",
    response_model=NotificationPrefsResponse,
    summary="Update notification preferences (consumer only)",
)
def update_notification_prefs(
    payload: NotificationPrefsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationPreferences:
    _require_consumer(current_user)
    prefs = _get_or_create_prefs(db, current_user.id)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(prefs, field, value)

    db.commit()
    db.refresh(prefs)
    return prefs


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_consumer(user: User) -> None:
    """Raise 403 if the user is not a consumer."""
    from models import UserTypeEnum
    if user.user_type != UserTypeEnum.consumer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Notification preferences are only available for consumer accounts.",
        )


def _get_or_create_prefs(db: Session, user_id: int) -> NotificationPreferences:
    """Return existing NotificationPreferences row, or create a default one."""
    prefs = (
        db.query(NotificationPreferences)
        .filter(NotificationPreferences.user_id == user_id)
        .first()
    )
    if prefs is None:
        prefs = NotificationPreferences(user_id=user_id)
        db.add(prefs)
        db.commit()
        db.refresh(prefs)
    return prefs
