"""
utils/security.py — Password hashing and JWT token utilities
"""

import os
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from jose import JWTError, jwt
from dotenv import load_dotenv

load_dotenv()

# ── Configuration ────────────────────────────────────────────────────────────
# No fallback: a known default key would let anyone forge login tokens, and the
# app would run fine while silently insecure. Refuse to start instead.
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise SystemExit(
        "SECRET_KEY is not set — refusing to start with a forgeable signing key.\n"
        "Add it to backend/.env; generate one with:\n"
        '  python3 -c "import secrets; print(secrets.token_hex(32))"'
    )

ALGORITHM         = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))


# ── Password helpers ─────────────────────────────────────────────────────────
def hash_password(plain: str) -> str:
    """Return bcrypt hash of the plain-text password."""
    return bcrypt.hashpw(plain.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain password against its bcrypt hash."""
    return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))


# ── JWT helpers ──────────────────────────────────────────────────────────────
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create and return a signed JWT access token."""
    payload = data.copy()
    expire = datetime.utcnow() + (
        expires_delta if expires_delta
        else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload.update({"exp": expire})
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """Decode a JWT token. Returns payload dict or None on failure."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
