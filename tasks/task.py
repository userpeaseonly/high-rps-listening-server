import asyncio
import logging
from celery_config import celery
from db import _test_db_connection
from tasks.repository import _process_outbox_batch, _publish_event_by_id
from datetime import datetime

logger = logging.getLogger(__name__)

# Get or create event loop for Celery workers
def get_event_loop():
    """Get or create an event loop for the current thread"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop

@celery.task(bind=True, max_retries=3)
def process_outbox_events(self):
    """
    Celery task to process outbox events.
    This runs as a separate process and doesn't affect the main Robyn server.
    """
    try:
        loop = get_event_loop()
        loop.run_until_complete(_process_outbox_batch())
        return {"status": "success", "processed_at": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error(f"Error in Celery outbox processor: {e}")
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))

@celery.task(bind=True, max_retries=5)
def publish_single_event(self, event_id: int):
    """
    Publish a single event to Kafka.
    This can be called immediately after saving an event for faster processing.
    """
    try:
        loop = get_event_loop()
        loop.run_until_complete(_publish_event_by_id(event_id))
        return {"status": "success", "event_id": event_id, "published_at": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error(f"Error publishing event {event_id}: {e}")
        raise self.retry(exc=e, countdown=30 * (2 ** self.request.retries))


# Health check task
@celery.task
def health_check():
    """Health check task for monitoring"""
    try:
        loop = get_event_loop()
        resp = loop.run_until_complete(_test_db_connection())
        logger.debug(f"Health check DB response: {resp}")
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "celery_outbox_processor"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
            "service": "celery_outbox_processor"
        }
