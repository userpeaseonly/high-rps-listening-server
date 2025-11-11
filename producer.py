#!/usr/bin/env python3
"""
Kafka Producer Service
Production-ready Kafka producer for integration with listening services
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError, KafkaTimeoutError
from enum import Enum

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MessagePriority(Enum):
    LOW = "low"
    NORMAL = "normal" 
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class ProducerConfig:
    """Producer configuration settings"""
    bootstrap_servers: str = "23.88.61.136:9092"
    default_topic: str = "raw_events"
    client_id: str = "time-pay-producer"
    acks: str = "all"
    enable_idempotence: bool = True
    retry_backoff_ms: int = 100
    request_timeout_ms: int = 30000
    compression_type: str = "gzip"
    max_retries: int = 5
    retry_delay: float = 1.0

@dataclass
class Message:
    """Standard message format for the time-pay ecosystem"""
    event_type: str
    data: Dict[str, Any]
    source: str
    priority: str = MessagePriority.NORMAL.value  # Store as string value
    message_id: Optional[str] = None
    timestamp: Optional[str] = None
    correlation_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    
    def __post_init__(self):
        if self.message_id is None:
            self.message_id = str(uuid.uuid4())
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()
        # Convert enum to string if passed as enum
        if isinstance(self.priority, MessagePriority):
            self.priority = self.priority.value

class KafkaProducerService:
    """Production-ready Kafka Producer Service"""
    
    def __init__(self, config: Optional[ProducerConfig] = None):
        self.config = config or ProducerConfig()
        self.producer: Optional[AIOKafkaProducer] = None
        self.is_running = False
        self.stats = {
            "messages_sent": 0,
            "messages_failed": 0,
            "total_bytes_sent": 0,
            "start_time": None
        }
        
    async def start(self) -> bool:
        """Initialize and start the producer"""
        try:
            logger.info(f"Starting Kafka Producer Service...")
            logger.info(f"Bootstrap servers: {self.config.bootstrap_servers}")
            logger.info(f"Default topic: {self.config.default_topic}")
            
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.config.bootstrap_servers,
                value_serializer=self._serialize_value,
                key_serializer=self._serialize_key,
                client_id=self.config.client_id,
                
                # Reliability settings
                acks=self.config.acks,
                enable_idempotence=self.config.enable_idempotence,
                retry_backoff_ms=self.config.retry_backoff_ms,
                request_timeout_ms=self.config.request_timeout_ms,
                compression_type=self.config.compression_type,
            )
            
            await self.producer.start()
            self.is_running = True
            self.stats["start_time"] = datetime.now()
            
            logger.info("✅ Kafka Producer Service started successfully!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to start Kafka Producer Service: {e}")
            return False
    
    async def stop(self):
        """Gracefully stop the producer"""
        if self.producer and self.is_running:
            try:
                logger.info("Stopping Kafka Producer Service...")
                await self.producer.stop()
                self.is_running = False
                logger.info("✅ Kafka Producer Service stopped successfully!")
            except Exception as e:
                logger.error(f"❌ Error stopping producer: {e}")
    
    async def send_message(
        self, 
        message: Message, 
        topic: Optional[str] = None,
        partition_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a message to Kafka
        
        Args:
            message: Message object to send
            topic: Optional topic override
            partition_key: Optional partition key for message routing
            
        Returns:
            Dict with send result information
        """
        if not self.is_running or not self.producer:
            raise RuntimeError("Producer service not started")
        
        target_topic = topic or self.config.default_topic
        key = partition_key or message.user_id or message.session_id
        
        # Add metadata to message
        message_dict = asdict(message)
        message_dict.update({
            "producer_timestamp": datetime.now().isoformat(),
            "topic": target_topic
        })
        
        for attempt in range(self.config.max_retries):
            try:
                logger.debug(f"Sending message {message.message_id} (attempt {attempt + 1})")
                
                record_metadata = await self.producer.send_and_wait(
                    topic=target_topic,
                    value=message_dict,
                    key=key,
                    timestamp_ms=int(time.time() * 1000)
                )
                
                # Update statistics
                self.stats["messages_sent"] += 1
                self.stats["total_bytes_sent"] += len(json.dumps(message_dict))
                
                result = {
                    "success": True,
                    "message_id": message.message_id,
                    "topic": record_metadata.topic,
                    "partition": record_metadata.partition,
                    "offset": record_metadata.offset,
                    "timestamp": record_metadata.timestamp,
                    "attempts": attempt + 1
                }
                
                logger.debug(f"✅ Message {message.message_id} sent to {target_topic}[{record_metadata.partition}]@{record_metadata.offset}")
                return result
                
            except KafkaTimeoutError as e:
                logger.warning(f"⏰ Timeout sending message {message.message_id} (attempt {attempt + 1}): {e}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay * (attempt + 1))
                    continue
                    
            except KafkaError as e:
                logger.error(f"❌ Kafka error sending message {message.message_id} (attempt {attempt + 1}): {e}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay * (attempt + 1))
                    continue
                    
            except Exception as e:
                logger.error(f"💥 Unexpected error sending message {message.message_id}: {e}")
                break
        
        # All retries failed
        self.stats["messages_failed"] += 1
        return {
            "success": False,
            "message_id": message.message_id,
            "error": "Failed after all retry attempts",
            "attempts": self.config.max_retries
        }
    
    async def send_batch(
        self, 
        messages: List[Message], 
        topic: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Send multiple messages efficiently
        
        Args:
            messages: List of Message objects
            topic: Optional topic override
            
        Returns:
            List of send results
        """
        if not messages:
            return []
            
        logger.info(f"Sending batch of {len(messages)} messages...")
        
        # Send messages concurrently
        tasks = [
            self.send_message(message, topic)
            for message in messages
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        successful = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
        failed = len(results) - successful
        
        logger.info(f"Batch complete: {successful} sent, {failed} failed")
        
        return [r if isinstance(r, dict) else {"success": False, "error": str(r)} for r in results]
    
    async def send_event(
        self,
        event_type: str,
        data: Dict[str, Any],
        source: str,
        priority: MessagePriority = MessagePriority.NORMAL,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        topic: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Convenience method for sending events directly
        
        Args:
            event_type: Type of event (e.g., "user_login", "payment_processed")
            data: Event payload data
            source: Source service/component name
            priority: Message priority level
            user_id: Optional user identifier
            session_id: Optional session identifier
            correlation_id: Optional correlation identifier for tracing
            topic: Optional topic override
            
        Returns:
            Send result dictionary
        """
        message = Message(
            event_type=event_type,
            data=data,
            source=source,
            priority=priority,
            user_id=user_id,
            session_id=session_id,
            correlation_id=correlation_id
        )
        
        return await self.send_message(message, topic)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get producer statistics"""
        uptime = None
        if self.stats["start_time"]:
            uptime = (datetime.now() - self.stats["start_time"]).total_seconds()
            
        return {
            **self.stats,
            "is_running": self.is_running,
            "uptime_seconds": uptime,
            "success_rate": (
                self.stats["messages_sent"] / 
                (self.stats["messages_sent"] + self.stats["messages_failed"])
                if (self.stats["messages_sent"] + self.stats["messages_failed"]) > 0 
                else 0
            )
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check"""
        if not self.is_running:
            return {"status": "down", "message": "Producer not running"}
        
        try:
            # Simple health check - try to create a test message without sending
            test_data = {"health_check": True, "timestamp": time.time()}
            serialized = self._serialize_value(test_data)
            
            return {
                "status": "up",
                "message": "Producer healthy",
                "serialization_test": len(serialized) > 0,
                "stats": self.get_stats()
            }
        except Exception as e:
            return {
                "status": "degraded", 
                "message": f"Health check failed: {e}",
                "stats": self.get_stats()
            }
    
    @staticmethod
    def _serialize_value(value: Any) -> bytes:
        """Serialize message value to bytes"""
        return json.dumps(value, default=str).encode("utf-8")
    
    @staticmethod
    def _serialize_key(key: Any) -> Optional[bytes]:
        """Serialize message key to bytes"""
        return str(key).encode("utf-8") if key else None

# Singleton instance for easy import
producer_service = None

async def get_producer_service(config: Optional[ProducerConfig] = None) -> KafkaProducerService:
    """Get or create producer service instance"""
    global producer_service
    
    if producer_service is None:
        producer_service = KafkaProducerService(config)
        await producer_service.start()
    
    return producer_service

async def cleanup_producer_service():
    """Cleanup producer service on shutdown"""
    global producer_service
    
    if producer_service:
        await producer_service.stop()
        producer_service = None

# Context manager for producer lifecycle
class ProducerServiceManager:
    """Context manager for producer service lifecycle"""
    
    def __init__(self, config: Optional[ProducerConfig] = None):
        self.config = config
        self.service = None
    
    async def __aenter__(self) -> KafkaProducerService:
        self.service = KafkaProducerService(self.config)
        await self.service.start()
        return self.service
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.service:
            await self.service.stop()

# Example usage and testing
async def example_usage():
    """Example of how to use the producer service"""
    
    # Configuration
    config = ProducerConfig(
        bootstrap_servers="23.88.61.136:9092",
        default_topic="raw_events",
        client_id="time-pay-listener"
    )
    
    # Method 1: Using context manager (recommended)
    async with ProducerServiceManager(config) as producer:
        
        # Send a simple event
        result = await producer.send_event(
            event_type="user_action",
            data={"action": "login", "timestamp": time.time()},
            source="auth_service",
            user_id="user_123",
            session_id="session_456"
        )
        print(f"Event sent: {result}")
        
        # Send a critical event
        result = await producer.send_event(
            event_type="payment_failed", 
            data={"amount": 100.0, "currency": "USD", "error": "insufficient_funds"},
            source="payment_service",
            priority=MessagePriority.CRITICAL,
            user_id="user_123"
        )
        print(f"Critical event sent: {result}")
        
        # Check health
        health = await producer.health_check()
        print(f"Health check: {health}")
        
        # Get statistics
        stats = producer.get_stats()
        print(f"Stats: {stats}")

if __name__ == "__main__":
    # Run example
    asyncio.run(example_usage())