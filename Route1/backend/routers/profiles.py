"""
routers/profiles.py — Profile settings endpoints for all user types.

All three user roles (farmer, organization, consumer) can update their
own profile information via PATCH /profiles/me.

Photos:
  POST   /profiles/me/avatar   (multipart upload → S3, see utils/storage.py)
  DELETE /profiles/me/avatar

Viewing another member:
  GET /profiles/{user_id}      logged-in members only; never exposes email

Consumer-only: also update notification preferences at
  GET  /profiles/me/notifications
  PATCH /profiles/me/notifications
"""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from database import get_db
from models import User, NotificationPreferences, UserTypeEnum
from routers.auth import get_current_user
from schemas import (
    ProfileUpdateRequest,
    ProfileUpdateResponse,
    PublicProfileResponse,
    NotificationPrefsUpdate,
    NotificationPrefsResponse,
)
from utils import storage

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

    # Farmers must always have a location (the browse map depends on it).
    # Omitted fields are fine; present-but-empty/null is rejected.
    if current_user.user_type == UserTypeEnum.farmer:
        for field in ("location_city", "location_region"):
            if field in update_data and not (update_data[field] or "").strip():
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Farmers must have a Minnesota city and region — "
                           "buyers use it to find listings near them.",
                )

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


# ── POST /profiles/me/avatar ─────────────────────────────────────────────────

@router.post(
    "/me/avatar",
    response_model=ProfileUpdateResponse,
    summary="Upload a profile photo (all roles)",
)
async def upload_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Accepts a JPG/PNG/WebP/HEIC-ish image, stores a 512px square WebP, and
    points the user's avatar_url at it.

    The declared content type is only a first filter — it's client-supplied and
    trivially spoofed, so the real check is whether Pillow can decode the bytes
    (utils/storage.py raises AvatarError if not).
    """
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Please choose an image file (JPG, PNG, or WebP).",
        )

    # Read with a hard ceiling rather than trusting any declared length: read
    # one byte past the limit, and if we got it, the file is too big.
    limit = storage.MAX_UPLOAD_MB * 1024 * 1024
    raw = await file.read(limit + 1)
    if len(raw) > limit:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"That photo is larger than {storage.MAX_UPLOAD_MB} MB. "
                   "Most phones can share a smaller copy.",
        )
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="That file was empty.",
        )

    try:
        url = storage.upload_avatar(current_user.id, raw)
    except storage.AvatarError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    previous = current_user.avatar_url
    current_user.avatar_url = url
    db.commit()
    db.refresh(current_user)

    # Only after the new photo is committed — a failed delete must never cost
    # the user the avatar they just uploaded.
    storage.delete_avatar(previous)
    return current_user


# ── DELETE /profiles/me/avatar ───────────────────────────────────────────────

@router.delete(
    "/me/avatar",
    response_model=ProfileUpdateResponse,
    summary="Remove the current profile photo",
)
def remove_avatar(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    previous = current_user.avatar_url
    current_user.avatar_url = None
    db.commit()
    db.refresh(current_user)
    storage.delete_avatar(previous)
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


# ── GET /profiles/{user_id} ──────────────────────────────────────────────────
#
# Registered after every "/me" route on purpose: FastAPI matches in declaration
# order, and this path would otherwise swallow "/profiles/me" and fail on the
# int conversion.

@router.get(
    "/{user_id}",
    response_model=PublicProfileResponse,
    summary="View another member's public profile",
)
def get_public_profile(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PublicProfileResponse:
    """
    The public face of a member — no email, no account state. Requires a login,
    matching the rest of the site: profiles are visible to the community, not
    to the open web.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="That member's profile isn't available.",
        )

    return PublicProfileResponse(
        id                = user.id,
        user_type         = user.user_type.value if user.user_type else "",
        full_name         = user.full_name,
        organization_name = user.organization_name,
        avatar_url        = user.avatar_url,
        tagline           = user.tagline,
        bio               = user.bio,
        year_started      = user.year_started,
        location_city     = user.location_city,
        location_region   = user.location_region,
        phone             = user.phone,
        member_since      = user.created_at,
    )


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
