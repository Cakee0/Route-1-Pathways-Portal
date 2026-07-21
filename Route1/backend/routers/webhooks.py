"""
routers/webhooks.py — Stripe webhook receiver (the confirmation source of truth).

Stripe calls POST /webhooks/stripe server-to-server after a hosted Checkout
payment. This endpoint is deliberately UNAUTHENTICATED — it is gated instead by
the Stripe signature (verified against STRIPE_WEBHOOK_SECRET), which is the only
thing that proves the request really came from Stripe. Never confirm a donation
from anything else (the browser success redirect can be forged or dropped).

Handled events:
  checkout.session.completed          — card payment finished (payment_status=paid)
  checkout.session.async_payment_succeeded — delayed method cleared later

Both funnel into confirm_paid_donation(), which is idempotent, so Stripe's
at-least-once delivery (retries) can never double-count a donation or double-
award points.
"""

import logging

from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from routers.donations import confirm_paid_donation
from routers.orders import confirm_paid_order
from utils import payments

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

_PAID_EVENTS = {"checkout.session.completed", "checkout.session.async_payment_succeeded"}


@router.post("/stripe", summary="Stripe webhook receiver (signature-verified)")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    if not payments.webhook_configured():
        # No signing secret means we cannot trust anything — refuse rather than
        # risk confirming an unverifiable event.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook is not configured.",
        )

    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")

    try:
        event = payments.verify_webhook(payload, signature)
    except Exception:
        # Malformed body or bad/forged signature — do not process.
        logger.warning("Stripe webhook rejected: signature verification failed.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature.")

    event_type = event.get("type")
    if event_type not in _PAID_EVENTS:
        # Acknowledge unhandled events with 200 so Stripe stops retrying them.
        logger.info("Stripe webhook: ignoring event type %s", event_type)
        return {"received": True, "handled": False}

    session = event["data"]["object"]

    # A completed session for an async payment method may still be unpaid; only
    # act once Stripe reports the money as captured.
    if session.get("payment_status") != "paid":
        logger.info("Stripe webhook: session %s not paid yet (%s) — waiting.",
                    session.get("id"), session.get("payment_status"))
        return {"received": True, "handled": False}

    payment_intent_id = session.get("payment_intent")
    if isinstance(payment_intent_id, dict):  # if expanded
        payment_intent_id = payment_intent_id.get("id")

    meta = session.get("metadata") or {}
    kind = meta.get("kind")

    # Dispatch by flow: "order" is a direct crop purchase; anything else
    # ("individual"/"group"/legacy) is a donation.
    if kind == "order":
        order_id = _extract_int(meta.get("order_id") or session.get("client_reference_id"))
        if order_id is None:
            logger.error("Stripe webhook: paid order session %s has no order_id.", session.get("id"))
            return {"received": True, "handled": False}
        confirm_paid_order(db, order_id, payment_intent_id)
        logger.info("Stripe webhook: confirmed order_id=%s from session %s", order_id, session.get("id"))
        return {"received": True, "handled": True}

    donation_id = _extract_int(meta.get("donation_id") or session.get("client_reference_id"))
    if donation_id is None:
        logger.error("Stripe webhook: paid session %s has no donation_id — cannot confirm.",
                     session.get("id"))
        # 200 so Stripe doesn't retry forever; this needs manual investigation.
        return {"received": True, "handled": False}

    confirm_paid_donation(db, donation_id, payment_intent_id)
    logger.info("Stripe webhook: confirmed donation_id=%s from session %s",
                donation_id, session.get("id"))
    return {"received": True, "handled": True}


def _extract_int(raw) -> int | None:
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None
