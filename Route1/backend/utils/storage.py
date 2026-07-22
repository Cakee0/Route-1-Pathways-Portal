"""
utils/storage.py — profile photo storage (S3 in production, disk in dev).

Follows the same contract as utils/emailer.py: read config from the
environment, and when it isn't configured, degrade to something that still
works locally rather than crashing. With AVATAR_BUCKET unset the app writes
under ./media/avatars and serves from the API host, so a developer needs no
AWS credentials to run the site.

    AVATAR_BUCKET       S3 bucket name, e.g. route1-media   (unset → local disk)
    AVATAR_PUBLIC_BASE  public URL base for that bucket
    AWS_REGION          default us-east-2

Credentials come from the EC2 instance role — boto3 discovers them on its own,
so no AWS keys live in .env.

Two things happen to every upload before it is stored:

  * It is re-encoded through Pillow, which drops EXIF. That matters more than
    it sounds: a farmer photographing their own farm would otherwise publish
    their home GPS coordinates in the file's metadata.
  * The object key gets a random suffix, so avatar URLs can't be enumerated by
    walking user ids. This is obscurity, not access control — anyone holding
    the URL can fetch it — but it stops the trivial scrape.
"""

import io
import logging
import os
import secrets
from pathlib import Path
from typing import Optional

from PIL import Image, UnidentifiedImageError

logger = logging.getLogger(__name__)

# Stored square, at a size that still looks sharp on a retina profile header.
AVATAR_PX      = 512
WEBP_QUALITY   = 80
MAX_UPLOAD_MB  = 5

# Local fallback (dev only) — mounted by main.py at /media when in use.
_LOCAL_DIR = Path(__file__).resolve().parent.parent / "media" / "avatars"


class AvatarError(Exception):
    """Raised when an upload isn't a usable image. Message is user-facing."""


def _config():
    return {
        "bucket": os.getenv("AVATAR_BUCKET"),
        "base":   (os.getenv("AVATAR_PUBLIC_BASE") or "").rstrip("/"),
        "region": os.getenv("AWS_REGION", "us-east-2"),
    }


def is_configured() -> bool:
    """True when uploads go to S3; False means the local-disk fallback."""
    cfg = _config()
    return bool(cfg["bucket"] and cfg["base"])


def _to_square_webp(raw: bytes) -> bytes:
    """Decode, center-crop to a square, downscale, re-encode as WebP."""
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()                      # forces a real decode; catches truncation
    except (UnidentifiedImageError, OSError) as exc:
        # Covers a .pdf renamed .jpg, and anything else that isn't an image.
        raise AvatarError("That file isn't an image we can read. Try a JPG or PNG.") from exc

    # Flatten transparency onto white; WebP keeps alpha, but a translucent
    # avatar over the page background reads as a rendering bug.
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        flat = Image.new("RGBA", img.size, (255, 255, 255, 255))
        flat.alpha_composite(img)
        img = flat.convert("RGB")
    else:
        img = img.convert("RGB")

    # ImageOps.fit center-crops to the target aspect, so portrait phone photos
    # become a face-centred square rather than a squashed one.
    from PIL import ImageOps
    img = ImageOps.fit(img, (AVATAR_PX, AVATAR_PX), method=Image.LANCZOS)

    out = io.BytesIO()
    img.save(out, format="WEBP", quality=WEBP_QUALITY)
    return out.getvalue()


def upload_avatar(user_id: int, raw: bytes) -> str:
    """
    Store a processed avatar for `user_id` and return its public URL.

    Raises AvatarError if the bytes aren't a decodable image.
    """
    data = _to_square_webp(raw)
    key  = f"avatars/{user_id}-{secrets.token_urlsafe(8)}.webp"
    cfg  = _config()

    if not is_configured():
        _LOCAL_DIR.mkdir(parents=True, exist_ok=True)
        (_LOCAL_DIR / Path(key).name).write_bytes(data)
        logger.info("AVATAR stored locally (AVATAR_BUCKET unset) → %s", key)
        return f"/media/{key}"

    import boto3   # imported lazily so local dev never needs boto3 installed

    boto3.client("s3", region_name=cfg["region"]).put_object(
        Bucket      = cfg["bucket"],
        Key         = key,
        Body        = data,
        ContentType = "image/webp",
        # Avatars are content-addressed by their random key, so a long cache is
        # safe: changing a photo writes a new key.
        CacheControl= "public, max-age=31536000, immutable",
    )
    logger.info("AVATAR uploaded → s3://%s/%s", cfg["bucket"], key)
    return f"{cfg['base']}/{key}"


def delete_avatar(url: Optional[str]) -> None:
    """
    Best-effort removal of a previously stored avatar.

    Never raises: a stale object costs a fraction of a cent, while a failure
    here must not block the user from changing their photo.
    """
    if not url:
        return
    cfg = _config()

    try:
        if not is_configured():
            name = Path(url).name
            if name:
                (_LOCAL_DIR / name).unlink(missing_ok=True)
            return

        if not url.startswith(cfg["base"] + "/"):
            return          # not ours (or the bucket was reconfigured)
        key = url[len(cfg["base"]) + 1:]

        import boto3
        boto3.client("s3", region_name=cfg["region"]).delete_object(
            Bucket=cfg["bucket"], Key=key,
        )
        logger.info("AVATAR deleted → %s", key)
    except Exception:
        logger.exception("AVATAR delete failed (ignored) → %s", url)
