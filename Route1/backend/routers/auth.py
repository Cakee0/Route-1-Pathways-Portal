"""
routers/auth.py — Registration and login endpoints for all three user types.

Supported user_type values: farmer | organization | consumer
Organizations also require org_subtype: restaurant | grocery_store | food_shelf
"""

import os

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from database import get_db
from models import User, UserTypeEnum
from schemas import (
    GoogleAuthRequest,
    GoogleAuthResponse,
    GoogleRegisterRequest,
    TokenResponse,
    UserProfileResponse,
    UserRegisterRequest,
)
from utils.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# ── Google sign-in configuration ──────────────────────────────────────────────
# The OAuth 2.0 Web client ID from Google Cloud Console. Must match the client_id
# the front end initialises Google Identity Services with.
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
_GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
_GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


def _verify_google_credential(credential: str) -> dict:
    """Validate a Google ID token and return its claims, or raise 401/503.

    Verification is delegated to Google's tokeninfo endpoint (Google checks the
    signature and expiry); we then confirm the audience, issuer, and that the
    email is verified. For higher throughput, swap this for local JWKS
    verification via the `google-auth` library.
    """
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google sign-in is not configured on the server (missing GOOGLE_CLIENT_ID).",
        )
    try:
        resp = httpx.get(
            _GOOGLE_TOKENINFO_URL, params={"id_token": credential}, timeout=10.0
        )
    except httpx.HTTPError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not reach Google to verify sign-in. Please try again.",
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Google credential.",
        )

    claims = resp.json()
    if claims.get("aud") != GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google credential was issued for a different application.",
        )
    if claims.get("iss") not in _GOOGLE_ISSUERS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Untrusted Google token issuer.",
        )
    # tokeninfo returns "email_verified" as the string "true"/"false".
    if str(claims.get("email_verified")).lower() != "true":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your Google account email is not verified.",
        )
    return claims


def _issue_token(user: User) -> str:
    return create_access_token({"sub": str(user.id), "type": str(user.user_type)})


# ── Shared dependency ─────────────────────────────────────────────────────────
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Decode JWT and return the authenticated User, or raise 401."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None or not user.is_active:
        raise credentials_exception
    return user


# ── POST /auth/register ───────────────────────────────────────────────────────
@router.post(
    "/register",
    response_model=UserProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user (farmer, organization, or consumer)",
)
def register(payload: UserRegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    new_user = User(
        email             = payload.email,
        hashed_password   = hash_password(payload.password),
        user_type         = payload.user_type,
        org_subtype       = payload.org_subtype,
        full_name         = payload.full_name,
        organization_name = payload.organization_name,
        location_city     = payload.location_city,
        location_region   = payload.location_region,
        phone             = payload.phone,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


# ── POST /auth/login ──────────────────────────────────────────────────────────
@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and receive a JWT access token",
)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == form_data.username).first()
    # Google-only accounts have no password; guide them to the Google button.
    if user and not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This account uses Google sign-in. Please continue with Google.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated.",
        )

    token = _issue_token(user)
    return TokenResponse(
        access_token = token,
        org_subtype  = user.org_subtype,
        user_type    = user.user_type,
        user_id      = user.id,
        email        = user.email,
    )


# ── POST /auth/google ─────────────────────────────────────────────────────────
@router.post(
    "/google",
    response_model=GoogleAuthResponse,
    summary="Sign in with Google, or discover that a new account is needed",
)
def google_auth(payload: GoogleAuthRequest, db: Session = Depends(get_db)):
    """Verify a Google credential and either log the user in or report that a
    role must be chosen first (new Google users)."""
    claims = _verify_google_credential(payload.credential)
    google_id = claims["sub"]
    email     = claims.get("email")
    full_name = claims.get("name")

    user = db.query(User).filter(User.google_id == google_id).first()

    # Auto-link: an existing password account with the same verified email
    # gets its Google identity attached the first time they use Google.
    #
    # SECURITY: the password is cleared on link. Registration doesn't verify
    # email ownership, so someone could pre-register this email with a password
    # they know; Google's verified credential proves the person signing in NOW
    # owns the email, so any pre-existing password must not retain access.
    # The account becomes Google-only (login endpoint explains this if a
    # password login is attempted).
    if user is None and email:
        user = db.query(User).filter(User.email == email).first()
        if user is not None and user.google_id is None:
            user.google_id = google_id
            user.hashed_password = None
            db.commit()
            db.refresh(user)

    if user is None:
        # Brand-new Google user — must pick a role before we create an account.
        return GoogleAuthResponse(
            needs_registration = True,
            email              = email,
            full_name          = full_name,
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated.",
        )

    return GoogleAuthResponse(
        needs_registration = False,
        access_token       = _issue_token(user),
        user_type          = user.user_type,
        org_subtype        = user.org_subtype,
        user_id            = user.id,
        email              = user.email,
    )


# ── POST /auth/google/complete ────────────────────────────────────────────────
@router.post(
    "/google/complete",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Finish Google sign-up by choosing an account type",
)
def google_complete(payload: GoogleRegisterRequest, db: Session = Depends(get_db)):
    """Create a password-less account for a new Google user after they choose a
    role. The credential is re-verified so the client can't forge the identity."""
    claims = _verify_google_credential(payload.credential)
    google_id = claims["sub"]
    email     = claims.get("email")
    full_name = claims.get("name")

    # If the account already exists (double-submit / raced with /auth/google),
    # just link + log them in rather than erroring.
    existing = (
        db.query(User)
        .filter((User.google_id == google_id) | (User.email == email))
        .first()
    )
    if existing is not None:
        if existing.google_id is None:
            # Same takeover guard as /auth/google: linking by email clears any
            # pre-existing password (see comment there for the rationale).
            existing.google_id = google_id
            existing.hashed_password = None
            db.commit()
            db.refresh(existing)
        return TokenResponse(
            access_token = _issue_token(existing),
            org_subtype  = existing.org_subtype,
            user_type    = existing.user_type,
            user_id      = existing.id,
            email        = existing.email,
        )

    new_user = User(
        email           = email,
        hashed_password = None,           # Google-only account
        google_id       = google_id,
        user_type       = payload.user_type,
        org_subtype     = payload.org_subtype,
        full_name       = full_name,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return TokenResponse(
        access_token = _issue_token(new_user),
        org_subtype  = new_user.org_subtype,
        user_type    = new_user.user_type,
        user_id      = new_user.id,
        email        = new_user.email,
    )


# ── GET /auth/me ─────────────────────────────────────────────────────────────
@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Return the currently authenticated user's profile",
)
def me(current_user: User = Depends(get_current_user)):
    return current_user
