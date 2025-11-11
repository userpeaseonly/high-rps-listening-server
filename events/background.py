import asyncio
import logging
from typing import List
from sqlalchemy import select
from db import AsyncSessionLocal
from outbox.models import OutboxEvent
from producer import get_producer_service, MessagePriority
from datetime import datetime

logger = logging.getLogger(__name__)

class OutboxProcessor:
    def __init__(self, batch_size: int = 50, poll_interval: float = 1.0):
        self.batch_size = batch_size
        self.poll_interval = poll_interval
        self.running = False
        self.producer = None
    
    async def start(self):
        """Start the background processor"""
        self.running = True
        self.producer = await get_producer_service()
        logger.info("Outbox processor started")
        
        # Start processing loop
        asyncio.create_task(self._process_loop())
    
    async def stop(self):
        """Stop the background processor"""
        self.running = False
        logger.info("Outbox processor stopped")
    
    async def _process_loop(self):
        """Main processing loop"""
        while self.running:
            try:
                await self._process_batch()
                await asyncio.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"Error in outbox processor: {e}")
                await asyncio.sleep(5)  # Back off on error
    
    async def _process_batch(self):
        """Process a batch of outbox events"""
        async with AsyncSessionLocal() as db:
            # Get unprocessed events
            result = await db.execute(
                select(OutboxEvent)
                .where(OutboxEvent.processed == False)
                .order_by(OutboxEvent.created_at)
                .limit(self.batch_size)
            )
            events = result.scalars().all()
            
            if not events:
                return
            
            logger.debug(f"Processing {len(events)} outbox events")
            
            for event in events:
                try:
                    # Send to Kafka
                    result = await self.producer.send_event(
                        event_type=event.event_type,
                        data=event.payload,
                        source="event-listener",
                        priority=MessagePriority.NORMAL,
                        correlation_id=str(event.id)
                    )
                    
                    if result["success"]:
                        # Mark as processed
                        event.processed = True
                        event.processed_at = datetime.utcnow()
                        await db.commit()
                        logger.debug(f"Published outbox event {event.id}")
                    else:
                        logger.warning(f"Failed to publish outbox event {event.id}: {result}")
                        
                except Exception as e:
                    logger.error(f"Error processing outbox event {event.id}: {e}")

# Global processor instance
outbox_processor = OutboxProcessor()

async def start_background_tasks():
    """Start all background tasks"""
    await outbox_processor.start()

async def stop_background_tasks():
    """Stop all background tasks"""
    await outbox_processor.stop()