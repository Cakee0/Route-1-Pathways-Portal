"""
models/messaging.py — Direct messaging ORM model.

conversation_id is a deterministic string key: "LOWER_ID:HIGHER_ID"
(e.g. "3:17") so that both participants refer to the same thread
without needing a separate conversations table.
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from database import Base


_MYSQL_ARGS = {
    "mysql_engine":  "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


class Message(Base):
    __tablename__  = "messages"
    __table_args__ = _MYSQL_ARGS

    id              = Column(Integer,     primary_key=True, index=True)
    conversation_id = Column(String(50),  nullable=False, index=True)  # "min_id:max_id"
    sender_id       = Column(Integer,     ForeignKey("users.id"), nullable=False)
    receiver_id     = Column(Integer,     ForeignKey("users.id"), nullable=False)
    content         = Column(Text,        nullable=False)
    is_read         = Column(Boolean,     default=False)
    created_at      = Column(DateTime,    default=datetime.utcnow, index=True)

    # Relationships
    sender   = relationship("User", foreign_keys=[sender_id],   back_populates="sent_messages")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="received_messages")

    def __repr__(self) -> str:
        return f"<Message id={self.id} conv={self.conversation_id}>"


def make_conversation_id(user_a: int, user_b: int) -> str:
    """Return a stable, deterministic conversation key for any two user IDs."""
    lo, hi = sorted([user_a, user_b])
    return f"{lo}:{hi}"
