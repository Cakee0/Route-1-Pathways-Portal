"""
routers/messaging.py — Direct-messaging endpoints.

Architecture:
  - conversation_id is a deterministic "LOWER_ID:HIGHER_ID" key.
  - No separate conversations table is needed — threads are reconstructed
    by querying messages for a given conversation_id.
  - Messages are marked read when the recipient fetches the conversation.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from database import get_db
from models import Message, User
from models.messaging import make_conversation_id
from routers.auth import get_current_user
from schemas import ConversationSummary, MessageCreate, MessageResponse

router = APIRouter(prefix="/messages", tags=["Messaging"])


# ── POST /messages — send a message ──────────────────────────────────────────

@router.post(
    "",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send a direct message to another user",
)
def send_message(
    payload: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.receiver_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot send a message to yourself.")

    receiver = (
        db.query(User)
        .filter(User.id == payload.receiver_id, User.is_active == True)  # noqa: E712
        .first()
    )
    if not receiver:
        raise HTTPException(status_code=404, detail="Recipient not found.")

    conv_id = make_conversation_id(current_user.id, payload.receiver_id)
    msg = Message(
        conversation_id = conv_id,
        sender_id       = current_user.id,
        receiver_id     = payload.receiver_id,
        content         = payload.content,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return _to_response(msg)


# ── GET /messages/conversations — list all threads ───────────────────────────

@router.get(
    "/conversations",
    response_model=List[ConversationSummary],
    summary="List all conversations for the current user",
)
def list_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    msgs = (
        db.query(Message)
        .filter(
            or_(
                Message.sender_id   == current_user.id,
                Message.receiver_id == current_user.id,
            )
        )
        .order_by(Message.created_at.desc())
        .all()
    )

    # Build one ConversationSummary per unique conversation_id
    seen: dict[str, ConversationSummary] = {}
    for msg in msgs:
        cid      = msg.conversation_id
        other    = msg.receiver if msg.sender_id == current_user.id else msg.sender
        other_id = other.id if other else (
            msg.receiver_id if msg.sender_id == current_user.id else msg.sender_id
        )

        if cid not in seen:
            seen[cid] = ConversationSummary(
                conversation_id = cid,
                other_user_id   = other_id,
                other_user_name = (
                    (other.full_name or other.organization_name) if other else None
                ),
                other_user_avatar_url = other.avatar_url if other else None,
                last_message    = msg.content,
                last_message_at = msg.created_at,
                unread_count    = 0,
            )

        if not msg.is_read and msg.receiver_id == current_user.id:
            s = seen[cid]
            seen[cid] = ConversationSummary(
                **{**s.model_dump(), "unread_count": s.unread_count + 1}
            )

    return list(seen.values())


# ── GET /messages/conversations/{cid} — fetch a thread ───────────────────────

@router.get(
    "/conversations/{conversation_id}",
    response_model=List[MessageResponse],
    summary="Retrieve all messages in a conversation",
)
def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Validate format and access rights
    parts = conversation_id.split(":")
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="Invalid conversation ID format.")
    try:
        id_a, id_b = int(parts[0]), int(parts[1])
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID format.")
    if current_user.id not in (id_a, id_b):
        raise HTTPException(status_code=403, detail="Access denied.")

    msgs = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .all()
    )

    # Mark incoming messages as read
    updated = False
    for msg in msgs:
        if msg.receiver_id == current_user.id and not msg.is_read:
            msg.is_read = True
            updated = True
    if updated:
        db.commit()

    return [_to_response(m) for m in msgs]


# ── PUT /messages/{msg_id}/read — explicit read receipt ──────────────────────

@router.put(
    "/{msg_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark a received message as read",
)
def mark_read(
    msg_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    msg = (
        db.query(Message)
        .filter(Message.id == msg_id, Message.receiver_id == current_user.id)
        .first()
    )
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found.")
    msg.is_read = True
    db.commit()


# ── Internal helper ───────────────────────────────────────────────────────────

def _to_response(msg: Message) -> MessageResponse:
    sender_name   = None
    receiver_name = None
    if msg.sender:
        sender_name   = msg.sender.full_name   or msg.sender.organization_name
    if msg.receiver:
        receiver_name = msg.receiver.full_name or msg.receiver.organization_name
    return MessageResponse(
        id              = msg.id,
        conversation_id = msg.conversation_id,
        sender_id       = msg.sender_id,
        receiver_id     = msg.receiver_id,
        content         = msg.content,
        is_read         = msg.is_read,
        created_at      = msg.created_at,
        sender_name     = sender_name,
        receiver_name   = receiver_name,
    )
