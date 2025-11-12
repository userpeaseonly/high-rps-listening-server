from sqlalchemy.ext.asyncio import AsyncSession
from outbox.models import OutboxEvent


async def add_to_outbox(db: AsyncSession, aggregate_id: str, aggregate_type: str, event_type: str, payload: dict):
    """Add event to outbox for eventual Kafka publishing"""
    outbox_event = OutboxEvent(
        aggregate_id=aggregate_id,
        aggregate_type=aggregate_type,
        event_type=event_type,
        payload=payload
    )
    db.add(outbox_event)
    await db.flush()
    return outbox_event
