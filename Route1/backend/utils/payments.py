"""
utils/payments.py — Stripe Checkout + webhook helpers (the money path).

Design (see OPERATIONS.local.md §12):
  * A donation is created `pending`, then a Stripe **Checkout Session** is
    opened server-side and the consumer is redirected to Stripe's hosted page.
  * Stripe calls POST /webhooks/stripe on success; the signed
    `checkout.session.completed` event — never the browser redirect — is what
    confirms the donation and awards points.

All money collects in ONE Route 1 Stripe account (platform-collected model);
farmers are paid out manually. Config comes from the environment:

    STRIPE_SECRET_KEY       sk_test_… / sk_live_…  (server-side secret)
    STRIPE_WEBHOOK_SECRET   whsec_…                (verifies webhook signatures)
    CHECKOUT_SUCCESS_URL    where Stripe returns after payment
    CHECKOUT_CANCEL_URL     where Stripe returns if the consumer backs out

Until STRIPE_SECRET_KEY is set, is_configured() is False and the donation
endpoints refuse with 503 — the app still boots and every non-payment feature
works unchanged (mirrors utils/emailer.py's "works before configured" stance).
Nothing here ever confirms a donation on its own; only the webhook does.
"""

import logging
import os

import stripe

logger = logging.getLogger(__name__)


def _secret_key() -> str | None:
    return os.getenv("STRIPE_SECRET_KEY")


def _webhook_secret() -> str | None:
    return os.getenv("STRIPE_WEBHOOK_SECRET")


def is_configured() -> bool:
    """True once a Stripe secret key is present — payments can be taken."""
    return bool(_secret_key())


def webhook_configured() -> bool:
    """True once the webhook signing secret is present — events can be verified."""
    return bool(_webhook_secret())


def _apply_key() -> None:
    """Point the Stripe SDK at our secret key for this call."""
    stripe.api_key = _secret_key()


def _success_url() -> str:
    # {CHECKOUT_SESSION_ID} is filled in by Stripe; donation_id lets the success
    # page poll GET /donations/{id} without trusting anything the browser sends.
    base = os.getenv("CHECKOUT_SUCCESS_URL", "https://route1pathways.app/#/donation/success")
    # Start the query with "?" unless the configured URL already has one. A "#"
    # (hash-routed SPA) is NOT a query, so it must not force "&" — the params
    # belong after the fragment path: .../#/donation/success?donation_id=…
    joiner = "&" if "?" in base else "?"
    return f"{base}{joiner}donation_id={{DONATION_ID}}&session_id={{CHECKOUT_SESSION_ID}}"


def _cancel_url() -> str:
    return os.getenv("CHECKOUT_CANCEL_URL", "https://route1pathways.app/#/donation/cancel")


def _site_base() -> str:
    """Origin of the SPA, derived from CHECKOUT_SUCCESS_URL (e.g. https://route1pathways.app)."""
    url = os.getenv("CHECKOUT_SUCCESS_URL", "https://route1pathways.app/#/donation/success")
    return url.split("/#/")[0] or "https://route1pathways.app"


def _create_session(
    *,
    ref_id: int,
    amount: float,
    currency: str,
    product_name: str,
    description: str,
    metadata: dict,
    success_url: str,
    cancel_url: str,
    customer_email: str | None = None,
) -> "stripe.checkout.Session":
    """
    Shared Checkout Session builder for every payment flow (donations, orders).
    Raises stripe.error.StripeError on failure; callers roll back their pending
    row so no orphan is left behind.
    """
    _apply_key()
    unit_amount = int(round(amount * 100))  # Stripe uses the smallest unit (cents)
    session = stripe.checkout.Session.create(
        mode="payment",
        client_reference_id=str(ref_id),
        customer_email=customer_email or None,
        line_items=[
            {
                "quantity": 1,
                "price_data": {
                    "currency": currency,
                    "unit_amount": unit_amount,
                    "product_data": {"name": product_name, "description": description},
                },
            }
        ],
        metadata=metadata,
        # Same metadata on the PaymentIntent so refunds/disputes in the Stripe
        # dashboard trace back to the originating row.
        payment_intent_data={"metadata": metadata},
        success_url=success_url,
        cancel_url=cancel_url,
    )
    return session


def create_checkout_session(
    *,
    donation_id: int,
    amount: float,
    currency: str,
    crop_name: str,
    org_name: str,
    kind: str,
    customer_email: str | None = None,
) -> "stripe.checkout.Session":
    """
    Open a hosted Checkout Session for one donation. `kind` is "individual" or
    "group" — echoed in metadata so the webhook can tell the flows apart.
    """
    metadata = {"donation_id": str(donation_id), "kind": kind}
    # kind lets the post-checkout page fire the right analytics event.
    success_url = _success_url().replace("{DONATION_ID}", str(donation_id)) + f"&kind={kind}"
    session = _create_session(
        ref_id=donation_id,
        amount=amount,
        currency=currency,
        product_name=f"Contribution — {crop_name}",
        description=f"Funds {crop_name} for {org_name} via Route 1",
        metadata=metadata,
        success_url=success_url,
        cancel_url=_cancel_url(),
        customer_email=customer_email,
    )
    logger.info(
        "Stripe Checkout Session %s opened for donation_id=%s ($%.2f %s, kind=%s)",
        session.id, donation_id, amount, currency, kind,
    )
    return session


def create_order_checkout_session(
    *,
    order_id: int,
    amount: float,
    currency: str,
    crop_name: str,
    quantity: float,
    unit: str,
    farmer_name: str,
    customer_email: str | None = None,
) -> "stripe.checkout.Session":
    """Open a hosted Checkout Session for a direct crop purchase (metadata kind='order')."""
    metadata = {"order_id": str(order_id), "kind": "order"}
    success_url = (
        f"{_site_base()}/#/order/success"
        f"?order_id={order_id}&session_id={{CHECKOUT_SESSION_ID}}"
    )
    cancel_url = f"{_site_base()}/#/order/cancel"
    session = _create_session(
        ref_id=order_id,
        amount=amount,
        currency=currency,
        product_name=f"{crop_name} — {quantity:g} {unit}",
        description=f"Purchase from {farmer_name} via Route 1",
        metadata=metadata,
        success_url=success_url,
        cancel_url=cancel_url,
        customer_email=customer_email,
    )
    logger.info(
        "Stripe Checkout Session %s opened for order_id=%s ($%.2f %s)",
        session.id, order_id, amount, currency,
    )
    return session


def verify_webhook(payload: bytes, signature: str) -> dict:
    """
    Verify a webhook's signature and return the parsed event.

    Raises ValueError on a malformed body and
    stripe.error.SignatureVerificationError on a bad/forged signature — the
    caller turns both into HTTP 400 so unverified events are never processed.
    """
    return stripe.Webhook.construct_event(
        payload=payload,
        sig_header=signature,
        secret=_webhook_secret(),
    )
