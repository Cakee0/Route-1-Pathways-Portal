"""
utils/notify.py — consumer notification triggers (audit G1).

Both triggers are consumer-opt-in via NotificationPreferences and deliver by
email through utils.emailer (async; log-only until SES is configured):

  - notify_new_opportunity — a new wishlist item whose cost falls inside a
    consumer's configured price range. Fires on item CREATION (previously
    this fired on every donation, which would have spammed matching
    consumers once emails became real).
  - notify_group_progress — a group donation just opened, or needs only one
    more donor. Fires on each join; the conditions themselves are one-shot.

Callers wrap these in try/except: a notification bug must never break the
money path.
"""

import logging

from sqlalchemy.orm import Session

from models import NotificationPreferences, User

from utils import emailer

logger = logging.getLogger(__name__)

_SITE = "https://route1pathways.app"
_FOOTER = (
    "\n\n—\nYou're receiving this because you turned on notifications in your "
    "Route 1 profile settings. You can turn them off any time under "
    f"Profile Settings → Notification Preferences.\n{_SITE}"
)


def _recipients(db: Session, flag_column):
    """(email, prefs) pairs for active users with the given toggle enabled."""
    return (
        db.query(User.email, NotificationPreferences)
        .join(NotificationPreferences, NotificationPreferences.user_id == User.id)
        .filter(flag_column == True, User.is_active == True)  # noqa: E712
        .all()
    )


def notify_new_opportunity(db: Session, item) -> None:
    """Email consumers whose donation price range matches a new wishlist item."""
    amount = float(item.total_amount_required)
    org = item.organization.organization_name or item.organization.full_name or "An organization"

    messages = []
    for email, pref in _recipients(db, NotificationPreferences.donation_notifications_enabled):
        lo = float(pref.donation_min_price) if pref.donation_min_price else 0.0
        hi = float(pref.donation_max_price) if pref.donation_max_price else float("inf")
        if not (lo <= amount <= hi):
            continue
        logger.info(
            "NOTIFICATION → user_id=%s: New donation opportunity '%s' for $%.2f",
            pref.user_id, item.crop_name, amount,
        )
        messages.append((
            email,
            f"New donation opportunity on Route 1: {item.crop_name} (${amount:.2f})",
            f"{org} just posted a wishlist item:\n\n"
            f"    {item.crop_name} — {float(item.quantity_needed):g} {item.quantity_unit}, "
            f"${amount:.2f} needed\n\n"
            f"It falls within the donation range you set. Log in to donate:\n{_SITE}"
            + _FOOTER,
        ))
    emailer.send_emails(messages)


def notify_group_progress(db: Session, gd) -> None:
    """Email group-donation subscribers when a group opens or is one donor away."""
    remaining = max(0, gd.donors_needed - gd.donors_count)
    one_away = remaining == 1
    just_opened = gd.donors_count == 1
    if not (one_away or just_opened):
        return

    crop = gd.wishlist_item.crop_name
    if one_away:
        subject = f"Route 1: the group donation for {crop} needs just 1 more donor!"
        body = (
            f"The group donation for {crop} is almost there — "
            f"${float(gd.amount_pledged):.2f} of ${float(gd.total_required):.2f} pledged, "
            f"and only one more donor is needed to fund it.\n\n"
            f"Be the one who completes it:\n{_SITE}"
        )
    else:
        subject = f"Route 1: a new group donation just opened for {crop}"
        body = (
            f"A group donation just opened for {crop} "
            f"(${float(gd.total_required):.2f} goal, {gd.donors_needed} donors needed).\n\n"
            f"Join in:\n{_SITE}"
        )

    messages = []
    for email, pref in _recipients(db, NotificationPreferences.group_donation_notifications_enabled):
        if one_away:
            logger.info(
                "NOTIFICATION → user_id=%s: Group donation %s needs just 1 more donor!",
                pref.user_id, gd.id,
            )
        else:
            logger.info(
                "NOTIFICATION → user_id=%s: New group donation opened for wishlist item %s",
                pref.user_id, gd.wishlist_item_id,
            )
        messages.append((email, subject, body + _FOOTER))
    emailer.send_emails(messages)
