"""
Kafka Service for Event Publishing
Simple synchronous approach for better reliability
"""
import logging
import json
import time
from typing import Dict, Any, Optional
from kafka import KafkaProducer
from kafka.errors import KafkaError, KafkaTimeoutError
import config

logger = logging.getLogger(__name__)

class KafkaService:
    """Simple synchronous Kafka producer service"""
    
    def __init__(self):
        self.producer = None
        self._initialize_producer()
    
    def _initialize_producer(self):
        """Initialize Kafka producer with retry logic"""
        max_retries = 5
        for attempt in range(max_retries):
            try:
                self.producer = KafkaProducer(
                    bootstrap_servers=['23.88.61.136:9092'],
                    value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
                    key_serializer=lambda k: str(k).encode('utf-8') if k else None,
                    acks='all',
                    retries=3,
                    max_in_flight_requests_per_connection=1,
                    enable_idempotence=True,
                    compression_type='gzip',
                    batch_size=16384,
                    linger_ms=10,
                    request_timeout_ms=30000,
                    retry_backoff_ms=100
                )
                logger.info("✅ Kafka producer initialized successfully")
                return
            except Exception as e:
                logger.error(f"Failed to initialize Kafka producer (attempt {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    logger.error("❌ Failed to initialize Kafka producer after all retries")
                    raise
                time.sleep(2 ** attempt)  # Exponential backoff
    
    def publish_event(
        self, 
        event_type: str, 
        data: Dict[str, Any], 
        topic: str = "raw_events",
        key: Optional[str] = None
    ) -> bool:
        """
        Publish an event to Kafka
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.producer:
            logger.error("Kafka producer not initialized")
            return False
        
        message = {
            "event_type": event_type,
            "data": data,
            "timestamp": time.time(),
            "source": "event-listener"
        }
        
        try:
            # Send message synchronously with timeout
            future = self.producer.send(
                topic=topic,
                value=message,
                key=key,
                timestamp_ms=int(time.time() * 1000)
            )
            
            # Wait for send to complete (synchronous)
            record_metadata = future.get(timeout=30)
            
            logger.debug(
                f"✅ Published {event_type} to {topic}[{record_metadata.partition}]@{record_metadata.offset}"
            )
            return True
            
        except KafkaTimeoutError as e:
            logger.error(f"⏰ Timeout publishing {event_type}: {e}")
            return False
        except KafkaError as e:
            logger.error(f"❌ Kafka error publishing {event_type}: {e}")
            return False
        except Exception as e:
            logger.error(f"💥 Unexpected error publishing {event_type}: {e}")
            return False
    
    def close(self):
        """Close the producer connection"""
        if self.producer:
            try:
                self.producer.close()
                logger.info("Kafka producer closed")
            except Exception as e:
                logger.error(f"Error closing Kafka producer: {e}")

# Global instance
_kafka_service = None

def get_kafka_service() -> KafkaService:
    """Get or create global Kafka service instance"""
    global _kafka_service
    if _kafka_service is None:
        _kafka_service = KafkaService()
    return _kafka_service