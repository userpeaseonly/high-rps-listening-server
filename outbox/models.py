from sqlalchemy import String, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
from db import Base

class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    aggregate_id: Mapped[str] = mapped_column(String, nullable=False)  # event.id
    aggregate_type: Mapped[str] = mapped_column(String, nullable=False)  # "Event" or "Heartbeat"
    event_type: Mapped[str] = mapped_column(String, nullable=False)  # "event.created", "heartbeat.created"
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
