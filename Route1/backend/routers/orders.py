"""
routers/orders.py — Direct crop purchase (consumer buys from a farmer listing).

Two-sided flow (see models/order.py):
  POST /orders/                 consumer requests to buy (qty + delivery)  → pending_farmer
  GET  /orders/mine             consumer's own orders
  GET  /orders/incoming         farmer's incoming order requests
  POST /orders/{id}/approve     farmer approves                            → approved
  POST /orders/{id}/decline     farmer declines                           → declined
  POST /orders/{id}/pay         consumer pays an approved order (Stripe)   → checkout_url
  POST /orders/{id}/cancel      consumer cancels before paying            → cancelled
  GET  /orders/{id}             either party polls one order

Payment mirrors the donation flow: /pay opens a Stripe Checkout Session and the
signed webhook (routers/webhooks.py → confirm_paid_order) is the sole thing that
marks an order `paid` and decrements the crop's available quantity. Money is
platform-collected; farmers are paid out manually. No reward points are awarded.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import (
    User, UserTypeEnum,
    FarmerCropInventory,
    CropOrder, OrderStatusEnum, DeliveryMethodEnum,
)
from routers.auth import get_current_user
from schemas import OrderCreateRequest, OrderResponse, OrderCheckoutResponse
from utils import payments, emailer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orders", tags=["Orders"])

_SITE = "https://route1pathways.app"


# ── Guards ────────────────────────────────────────────────────────────────────

def _require_consumer(user: User) -> None:
    if user.user_type != UserTypeEnum.consumer:
        raise HTTPException(status_code=403, detail="Only consumer accounts can place orders.")


def _require_farmer(user: User) -> None:
    if user.user_type != UserTypeEnum.farmer:
        raise HTTPException(status_code=403, detail="Only farmer accounts can manage incoming orders.")


def _require_payments_configured() -> None:
    if not payments.is_configured():
        raise HTTPException(status_code=503, detail="Payments are not available yet. Please try again later.")


def _display_name(u: User | None) -> str | None:
    if not u:
        return None
    return u.full_name or u.organization_name or None


def _method_label(method) -> str:
    """Human-readable statement of who delivers, for emails."""
    if method == DeliveryMethodEnum.consumer_pickup:
        return "The buyer will pick up from the farmer."
    return "The farmer will deliver to the buyer's address."


def _order_response(o: CropOrder) -> OrderResponse:
    return OrderResponse(
        id=o.id,
        consumer_id=o.consumer_id,
        consumer_name=_display_name(o.consumer),
        farmer_id=o.farmer_id,
        farmer_name=_display_name(o.farmer),
        crop_id=o.crop_id,
        crop_name=o.crop.crop_name if o.crop else "(removed listing)",
        quantity=float(o.quantity),
        quantity_unit=o.quantity_unit,
        unit_price=float(o.unit_price),
        total_amount=float(o.total_amount),
        currency=o.currency,
        delivery_method=o.delivery_method,
        delivery_name=o.delivery_name,
        delivery_address=o.delivery_address,
        delivery_phone=o.delivery_phone,
        delivery_notes=o.delivery_notes,
        status=o.status,
        created_at=o.created_at,
    )


# ── POST /orders/ — consumer creates a purchase request ───────────────────────

@router.post(
    "/",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Consumer requests to buy a quantity of a crop (awaits farmer approval)",
)
def create_order(
    payload: OrderCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrderResponse:
    _require_consumer(current_user)

    crop = db.query(FarmerCropInventory).filter(FarmerCropInventory.id == payload.crop_id).first()
    if not crop or not crop.is_available:
        raise HTTPException(status_code=404, detail="Crop listing not found or no longer available.")
    if crop.price_per_unit is None:
        raise HTTPException(
            status_code=422,
            detail="This listing is priced on request — message the farmer to arrange a price.",
        )
    if payload.quantity > float(crop.quantity_available):
        raise HTTPException(
            status_code=422,
            detail=f"Only {float(crop.quantity_available):g} {crop.quantity_unit} are available.",
        )

    unit_price = float(crop.price_per_unit)
    total = round(payload.quantity * unit_price, 2)

    # A delivery address is required when the farmer delivers; for pickup it's
    # optional (the buyer goes to the farmer), so fall back to a clear default.
    address = (payload.delivery_address or "").strip()
    if payload.delivery_method == DeliveryMethodEnum.farmer_delivers and not address:
        raise HTTPException(status_code=422, detail="A delivery address is required when the farmer delivers.")
    if not address:
        address = "Buyer will pick up from the farmer."

    order = CropOrder(
        consumer_id=current_user.id,
        farmer_id=crop.farmer_id,
        crop_id=crop.id,
        quantity=payload.quantity,
        quantity_unit=crop.quantity_unit,
        unit_price=unit_price,
        total_amount=total,
        currency="usd",
        delivery_method=payload.delivery_method,
        delivery_name=payload.delivery_name.strip(),
        delivery_address=address,
        delivery_phone=(payload.delivery_phone or "").strip() or None,
        delivery_notes=(payload.delivery_notes or "").strip() or None,
        status=OrderStatusEnum.pending_farmer,
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    _notify_farmer_new_order(db, order, crop)
    return _order_response(order)


# ── GET /orders/mine — consumer's orders ──────────────────────────────────────

@router.get("/mine", response_model=List[OrderResponse], summary="Consumer's own orders")
def my_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[OrderResponse]:
    _require_consumer(current_user)
    orders = (
        db.query(CropOrder)
        .options(joinedload(CropOrder.crop), joinedload(CropOrder.farmer))
        .filter(CropOrder.consumer_id == current_user.id)
        .order_by(CropOrder.created_at.desc())
        .all()
    )
    return [_order_response(o) for o in orders]


# ── GET /orders/incoming — farmer's incoming requests ─────────────────────────

@router.get("/incoming", response_model=List[OrderResponse], summary="Farmer's incoming order requests")
def incoming_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[OrderResponse]:
    _require_farmer(current_user)
    orders = (
        db.query(CropOrder)
        .options(joinedload(CropOrder.crop), joinedload(CropOrder.consumer))
        .filter(CropOrder.farmer_id == current_user.id)
        .order_by(CropOrder.created_at.desc())
        .all()
    )
    return [_order_response(o) for o in orders]


# ── POST /orders/{id}/approve | /decline — farmer decision ────────────────────

@router.post("/{order_id}/approve", response_model=OrderResponse, summary="Farmer approves an order")
def approve_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrderResponse:
    _require_farmer(current_user)
    order = db.query(CropOrder).filter(CropOrder.id == order_id).with_for_update().first()
    if not order or order.farmer_id != current_user.id:
        raise HTTPException(status_code=404, detail="Order not found.")
    if order.status != OrderStatusEnum.pending_farmer:
        raise HTTPException(status_code=409, detail="This order is not awaiting your approval.")
    order.status = OrderStatusEnum.approved
    db.commit()
    db.refresh(order)
    _notify_consumer_decision(db, order, approved=True)
    return _order_response(order)


@router.post("/{order_id}/decline", response_model=OrderResponse, summary="Farmer declines an order")
def decline_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrderResponse:
    _require_farmer(current_user)
    order = db.query(CropOrder).filter(CropOrder.id == order_id).with_for_update().first()
    if not order or order.farmer_id != current_user.id:
        raise HTTPException(status_code=404, detail="Order not found.")
    if order.status != OrderStatusEnum.pending_farmer:
        raise HTTPException(status_code=409, detail="This order is not awaiting your approval.")
    order.status = OrderStatusEnum.declined
    db.commit()
    db.refresh(order)
    _notify_consumer_decision(db, order, approved=False)
    return _order_response(order)


# ── POST /orders/{id}/pay — consumer pays an approved order ────────────────────

@router.post("/{order_id}/pay", response_model=OrderCheckoutResponse, summary="Consumer pays an approved order")
def pay_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrderCheckoutResponse:
    _require_consumer(current_user)
    _require_payments_configured()

    order = db.query(CropOrder).filter(CropOrder.id == order_id).first()
    if not order or order.consumer_id != current_user.id:
        raise HTTPException(status_code=404, detail="Order not found.")
    if order.status != OrderStatusEnum.approved:
        raise HTTPException(
            status_code=409,
            detail="This order isn't ready to pay — the farmer must approve it first.",
        )

    # Re-check stock right before charging (the listing may have changed since approval).
    crop = db.query(FarmerCropInventory).filter(FarmerCropInventory.id == order.crop_id).first()
    if not crop or not crop.is_available or float(crop.quantity_available) < float(order.quantity):
        raise HTTPException(status_code=409, detail="There is no longer enough stock to fulfil this order.")

    try:
        session = payments.create_order_checkout_session(
            order_id=order.id,
            amount=float(order.total_amount),
            currency=order.currency,
            crop_name=crop.crop_name,
            quantity=float(order.quantity),
            unit=order.quantity_unit,
            farmer_name=_display_name(order.farmer) or "the farmer",
            customer_email=current_user.email,
        )
        order.stripe_session_id = session.id
        db.commit()
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception("Stripe Checkout Session creation failed for order_id=%s", order_id)
        raise HTTPException(status_code=502, detail="Could not start the payment. Please try again.")

    if not session.url:
        raise HTTPException(status_code=502, detail="Payment provider did not return a checkout URL.")
    return OrderCheckoutResponse(order_id=order.id, checkout_url=session.url, status=order.status)


# ── POST /orders/{id}/cancel — consumer cancels before paying ─────────────────

@router.post("/{order_id}/cancel", response_model=OrderResponse, summary="Consumer cancels an unpaid order")
def cancel_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrderResponse:
    _require_consumer(current_user)
    order = db.query(CropOrder).filter(CropOrder.id == order_id).with_for_update().first()
    if not order or order.consumer_id != current_user.id:
        raise HTTPException(status_code=404, detail="Order not found.")
    if order.status not in (OrderStatusEnum.pending_farmer, OrderStatusEnum.approved):
        raise HTTPException(status_code=409, detail="This order can no longer be cancelled.")
    order.status = OrderStatusEnum.cancelled
    db.commit()
    db.refresh(order)
    return _order_response(order)


# ── GET /orders/{order_id} — either party polls (declared last) ───────────────
# After /mine and /incoming so those specific paths aren't shadowed by "{id}".

@router.get("/{order_id}", response_model=OrderResponse, summary="Fetch one order (buyer or seller)")
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrderResponse:
    order = (
        db.query(CropOrder)
        .options(joinedload(CropOrder.crop), joinedload(CropOrder.farmer), joinedload(CropOrder.consumer))
        .filter(CropOrder.id == order_id)
        .first()
    )
    if not order or current_user.id not in (order.consumer_id, order.farmer_id):
        raise HTTPException(status_code=404, detail="Order not found.")
    return _order_response(order)


# ── Confirmation (called ONLY by the Stripe webhook) ──────────────────────────

def confirm_paid_order(db: Session, order_id: int, payment_intent_id: str | None) -> None:
    """
    Mark an approved order paid and decrement the crop's available quantity.
    Idempotent: the row lock serialises concurrent webhook deliveries and the
    status guard makes retries a no-op.
    """
    order = db.query(CropOrder).filter(CropOrder.id == order_id).with_for_update().first()
    if not order:
        logger.warning("Webhook confirm: order_id=%s not found — ignoring.", order_id)
        return
    if order.status != OrderStatusEnum.approved:
        logger.info("Webhook confirm: order_id=%s is %s — no-op.", order_id, order.status)
        return

    order.status = OrderStatusEnum.paid
    if payment_intent_id:
        order.stripe_payment_intent_id = payment_intent_id

    crop = (
        db.query(FarmerCropInventory)
        .filter(FarmerCropInventory.id == order.crop_id)
        .with_for_update()
        .first()
    )
    if crop:
        remaining = float(crop.quantity_available) - float(order.quantity)
        if remaining < 0:
            logger.warning("Order %s oversold crop %s by %.2f", order.id, crop.id, -remaining)
            remaining = 0
        crop.quantity_available = remaining
        if remaining <= 0:
            crop.is_available = False

    db.commit()
    _notify_farmer_paid(db, order)


# ── Notifications (best-effort; never break the money path) ───────────────────

def _notify_farmer_new_order(db: Session, order: CropOrder, crop: FarmerCropInventory) -> None:
    try:
        if not order.farmer or not order.farmer.email:
            return
        buyer = _display_name(order.consumer) or "A buyer"
        emailer.send_emails([(
            order.farmer.email,
            f"New order request on Route 1: {crop.crop_name}",
            f"{buyer} wants to buy {float(order.quantity):g} {order.quantity_unit} of "
            f"{crop.crop_name} for ${float(order.total_amount):.2f}.\n\n"
            f"Delivery: {_method_label(order.delivery_method)}\n"
            f"Approving this order confirms you agree to that delivery arrangement.\n\n"
            f"Log in to approve or decline this request:\n{_SITE}/#/orders\n",
        )])
    except Exception:
        logger.exception("order new-request notification failed")


def _notify_consumer_decision(db: Session, order: CropOrder, approved: bool) -> None:
    try:
        if not order.consumer or not order.consumer.email:
            return
        crop_name = order.crop.crop_name if order.crop else "your order"
        if approved:
            subject = f"Your Route 1 order was approved: {crop_name}"
            body = (
                f"Good news — the farmer approved your order for {crop_name} "
                f"(${float(order.total_amount):.2f}).\n\n"
                f"Delivery: {_method_label(order.delivery_method)}\n\n"
                f"Log in to pay and complete it:\n{_SITE}/#/orders\n"
            )
        else:
            subject = f"Your Route 1 order was declined: {crop_name}"
            body = (
                f"The farmer was unable to fulfil your order for {crop_name}. "
                f"You have not been charged.\n\n{_SITE}/#/orders\n"
            )
        emailer.send_emails([(order.consumer.email, subject, body)])
    except Exception:
        logger.exception("order decision notification failed")


def _notify_farmer_paid(db: Session, order: CropOrder) -> None:
    try:
        if not order.farmer or not order.farmer.email:
            return
        crop_name = order.crop.crop_name if order.crop else "an order"
        emailer.send_emails([(
            order.farmer.email,
            f"Order paid on Route 1: {crop_name}",
            f"{_display_name(order.consumer) or 'The buyer'} has paid for "
            f"{float(order.quantity):g} {order.quantity_unit} of {crop_name} "
            f"(${float(order.total_amount):.2f}).\n\n"
            f"Delivery: {_method_label(order.delivery_method)}\n"
            f"Details:\n{order.delivery_name}\n{order.delivery_address}\n"
            f"{('Phone: ' + order.delivery_phone) if order.delivery_phone else ''}\n"
            f"{('Notes: ' + order.delivery_notes) if order.delivery_notes else ''}\n\n"
            f"Arrange delivery with the buyer:\n{_SITE}/#/orders\n",
        )])
    except Exception:
        logger.exception("order paid notification failed")
