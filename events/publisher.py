import asyncio
import logging
from typing import Optional
from producer import get_producer_service, MessagePriority, Message

logger = logging.getLogger(__name__)

class EventPublisher:
    def __init__(self):
        self.producer = None
        
    async def get_producer(self):
        if not self.producer:
            self.producer = await get_producer_service()
        return self.producer
    
    async def publish_event_async(self, event_data: dict, event_type: str, priority: MessagePriority = MessagePriority.NORMAL):
        """Publish event asynchronously without blocking the main request"""
        try:
            producer = await self.get_producer()
            result = await producer.send_event(
                event_type=event_type,
                data=event_data,
                source="event-listener",
                priority=priority
            )
            if result["success"]:
                logger.info(f"Successfully published {event_type} to Kafka")
            else:
                logger.error(f"Failed to publish {event_type}: {result}")
        except Exception as e:
            logger.error(f"Error publishing {event_type} to Kafka: {e}")
    
    def publish_event_background(self, event_data: dict, event_type: str, priority: MessagePriority = MessagePriority.NORMAL):
        """Fire-and-forget background publishing"""
        asyncio.create_task(self.publish_event_async(event_data, event_type, priority))

# Singleton
event_publisher = EventPublisher()
