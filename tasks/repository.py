import logging
from sqlalchemy import select, update
from db import AsyncSessionLocal
from outbox.crud import OutboxEvent
from producer import get_producer_service, MessagePriority
from datetime import datetime

logger = logging.getLogger(__name__)


async def _process_outbox_batch(batch_size: int = 100):
    """Process a batch of unprocessed outbox events"""
    try:
        async with AsyncSessionLocal() as db:
            # Get unprocessed events
            result = await db.execute(
                select(OutboxEvent)
                .where(OutboxEvent.processed == False)
                .order_by(OutboxEvent.created_at)
                .limit(batch_size)
            )
            events = result.scalars().all()
            if not events:
                logger.debug("No outbox events to process")
                return
            
            logger.info(f"Processing {len(events)} outbox events")
            
            # Get producer service
            producer = await get_producer_service()
            
            processed_count = 0
            failed_count = 0
            
            for event in events:
                try:
                    # Send to Kafka
                    result = await producer.send_event(
                        event_type=event.event_type,
                        data=event.payload,
                        source="event-listener",
                        priority=MessagePriority.NORMAL,
                        correlation_id=str(event.id)
                    )
                    
                    if result["success"]:
                        # Mark as processed
                        await db.execute(
                            update(OutboxEvent)
                            .where(OutboxEvent.id == event.id)
                            .values(
                                processed=True,
                                processed_at=datetime.utcnow()
                            )
                        )
                        processed_count += 1
                        logger.debug(f"Published outbox event {event.id} to Kafka")
                    else:
                        failed_count += 1
                        logger.warning(f"Failed to publish outbox event {event.id}: {result}")
                        
                except Exception as e:
                    failed_count += 1
                    logger.error(f"Error processing outbox event {event.id}: {e}")
            
            # Commit all processed events at once
            await db.commit()
            
            if processed_count > 0 or failed_count > 0:
                logger.info(f"Outbox batch complete: {processed_count} processed, {failed_count} failed")
                
    except Exception as e:
        logger.error(f"Error in outbox batch processing: {e}")
        raise

async def _publish_event_by_id(event_id: int):
    """Publish a specific event by ID"""
    try:
        async with AsyncSessionLocal() as db:
            # Get the specific event
            result = await db.execute(
                select(OutboxEvent)
                .where(OutboxEvent.id == event_id)
                .where(OutboxEvent.processed == False)
            )
            event = result.scalar_one_or_none()
            
            if not event:
                logger.warning(f"Outbox event {event_id} not found or already processed")
                return
            
            # Get producer service
            producer = await get_producer_service()
            
            # Send to Kafka
            result = await producer.send_event(
                event_type=event.event_type,
                data=event.payload,
                source="event-listener",
                priority=MessagePriority.HIGH,  # Higher priority for single events
                correlation_id=str(event.id)
            )
            
            if result["success"]:
                # Mark as processed
                await db.execute(
                    update(OutboxEvent)
                    .where(OutboxEvent.id == event.id)
                    .values(
                        processed=True,
                        processed_at=datetime.utcnow()
                    )
                )
                await db.commit()
                logger.info(f"Successfully published single event {event_id} to Kafka")
            else:
                logger.error(f"Failed to publish single event {event_id}: {result}")
                raise Exception(f"Failed to publish event: {result}")
                
    except Exception as e:
        logger.error(f"Error publishing single event {event_id}: {e}")
        raise