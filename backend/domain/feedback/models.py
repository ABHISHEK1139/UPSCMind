"""
Feedback Domain Models
═══════════════════════════════════════════════════════════════
Database schema for user feedback on generated answers.
Registered on the shared Base so init_db() creates the table.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text

# Use the shared Base from core.database
from core.database import Base


class Feedback(Base):
    """Durable record of a student's feedback on a generated answer."""

    __tablename__ = "feedback"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(255), nullable=False, index=True)
    rating = Column(Integer, nullable=False)
    corrections = Column(Text, nullable=True)
    comments = Column(Text, nullable=True)
    domain = Column(String(100), nullable=True)
    collected_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
