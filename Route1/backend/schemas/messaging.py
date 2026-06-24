"""
schemas/messaging.py — Pydantic models for the direct-messaging system.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class MessageCreate(BaseModel):
    receiver_id: int
    content:     str

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id:              int
    conversation_id: str
    sender_id:       int
    receiver_id:     int
    content:         str
    is_read:         bool
    created_at:      datetime
    sender_name:     Optional[str] = None
    receiver_name:   Optional[str] = None

    model_config = {"from_attributes": True}


class ConversationSummary(BaseModel):
    conversation_id: str
    other_user_id:   int
    other_user_name: Optional[str]
    last_message:    Optional[str]
    last_message_at: Optional[datetime]
    unread_count:    int

    model_config = {"from_attributes": True}
