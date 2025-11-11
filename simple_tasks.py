"""
Celery Tasks for Event Processing
Best practices with synchronous operations
"""
import logging
from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy import create_engine, select, update, text
from sqlalchemy.orm import sessionmaker
from celery import Celery
import config
from kafka_service import get_kafka_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Synchronous database setup for Celery workers
sync_engine = create_engine(config.DATABASE_URL.replace('+asyncpg', ''))
SyncSessionLocal = sessionmaker(bind=sync_engine)

# Celery app
celery_app = Celery(
    'event_processor',
    broker=config.REDIS_URL,
    backend=config.REDIS_URL
)

# Configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    
    # Beat schedule
    beat_schedule={
        'process-failed-events': {
            'task': 'simple_tasks.process_failed_outbox_events',
            'schedule': 60.0,  # Every 1 minute
        },
    },
)

@celery_app.task(bind=True, max_retries=3)
def publish_event_immediately(self, outbox_event_id: int):
    """
    Publish a single event immediately after saving to database
    """
    try:
        with SyncSessionLocal() as db:
            # Get the outbox event
            result = db.execute(
                text("SELECT id, event_type, payload FROM outbox_events WHERE id = :id AND processed = false"),
                {"id": outbox_event_id}
            )
            row = result.fetchone()
            
            if not row:
                logger.warning(f"Outbox event {outbox_event_id} not found or already processed")
                return {"status": "not_found", "event_id": outbox_event_id}
            
            event_id, event_type, payload = row
            
            # Publish to Kafka
            kafka_service = get_kafka_service()
            success = kafka_service.publish_event(
                event_type=event_type,
                data=payload,
                topic="raw_events",
                key=str(event_id)
            )
            
            if success:
                # Mark as processed
                db.execute(
                    text("UPDATE outbox_events SET processed = true, processed_at = :now WHERE id = :id"),
                    {"now": datetime.utcnow(), "id": event_id}
                )
                db.commit()
                
                logger.info(f"✅ Successfully published event {event_id} to Kafka")
                return {"status": "success", "event_id": event_id}
            else:
                # Retry the task
                logger.warning(f"Failed to publish event {event_id}, will retry")
                raise Exception(f"Failed to publish event {event_id} to Kafka")
                
    except Exception as e:
        logger.error(f"Error processing event {outbox_event_id}: {e}")
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))

@celery_app.task
def process_failed_outbox_events():
    """
    Process unprocessed outbox events (runs every 1 minute)
    This is the fallback mechanism for failed immediate publishes
    """
    try:
        with SyncSessionLocal() as db:
            # Get unprocessed events older than 30 seconds
            result = db.execute(
                text("""
                    SELECT id, event_type, payload 
                    FROM outbox_events 
                    WHERE processed = false 
                      AND created_at < NOW() - INTERVAL '30 seconds'
                    ORDER BY created_at 
                    LIMIT 100
                """)
            )
            events = result.fetchall()
            
            if not events:
                logger.debug("No failed outbox events to process")
                return {"status": "no_events", "processed": 0}
            
            logger.info(f"Processing {len(events)} failed outbox events")
            
            kafka_service = get_kafka_service()
            processed_count = 0
            failed_count = 0
            
            for event_id, event_type, payload in events:
                try:
                    # Attempt to publish
                    success = kafka_service.publish_event(
                        event_type=event_type,
                        data=payload,
                        topic="raw_events",
                        key=str(event_id)
                    )
                    
                    if success:
                        # Mark as processed
                        db.execute(
                            text("UPDATE outbox_events SET processed = true, processed_at = :now WHERE id = :id"),
                            {"now": datetime.utcnow(), "id": event_id}
                        )
                        processed_count += 1
                        logger.debug(f"✅ Processed failed event {event_id}")
                    else:
                        failed_count += 1
                        logger.warning(f"❌ Still failed to process event {event_id}")
                        
                except Exception as e:
                    failed_count += 1
                    logger.error(f"Error processing failed event {event_id}: {e}")
            
            # Commit all successful updates
            db.commit()
            
            result = {
                "status": "completed",
                "processed": processed_count,
                "failed": failed_count,
                "total": len(events)
            }
            
            if processed_count > 0 or failed_count > 0:
                logger.info(f"Fallback processing complete: {processed_count} processed, {failed_count} failed")
            
            return result
            
    except Exception as e:
        logger.error(f"Error in fallback processing: {e}")
        return {"status": "error", "error": str(e)}

@celery_app.task
def health_check():
    """Health check for monitoring"""
    try:
        # Test database
        with SyncSessionLocal() as db:
            db.execute(text("SELECT 1"))
        
        # Test Kafka
        kafka_service = get_kafka_service()
        # Simple test - kafka_service initialization already tests connection
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "celery_event_processor"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
            "service": "celery_event_processor"
        }

# Helper function to trigger immediate publishing
def trigger_immediate_publish(outbox_event_id: int):
    """
    Trigger immediate publishing of an event
    Call this right after saving to database
    """
    publish_event_immediately.delay(outbox_event_id)