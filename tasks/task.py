import asyncio
import logging
from datetime import datetime, timezone
from celery_config import celery
from db import _test_db_connection
from tasks.repository import _process_outbox_batch, _publish_event_by_id

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
        return {"status": "success", "processed_at": datetime.now(timezone.utc).isoformat()}
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
        return {"status": "success", "event_id": event_id, "published_at": datetime.now(timezone.utc).isoformat()}
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
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": "celery_outbox_processor"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": "celery_outbox_processor"
        }

@celery.task(bind=True, max_retries=3)
def cleanup_processed_outbox_events(self):
    """
    Cleanup old processed outbox events to prevent unbounded table growth.
    Runs periodically based on OUTBOX_CLEANUP_INTERVAL configuration.
    """
    try:
        import config
        loop = get_event_loop()
        from tasks.repository import _cleanup_old_outbox_events
        deleted_count = loop.run_until_complete(_cleanup_old_outbox_events(config.OUTBOX_RETENTION_HOURS))
        logger.info(f"Cleaned up {deleted_count} old outbox events")
        return {
            "status": "success",
            "deleted_count": deleted_count,
            "cleaned_at": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Error cleaning up outbox events: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=300)  # Retry after 5 minutes
