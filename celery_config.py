import asyncio
from celery import Celery
from celery.signals import worker_process_init
import config

# Configure Celery
celery = Celery(
    "event_processor",
    broker=config.REDIS_URL,
    backend=config.REDIS_URL,
    include=['tasks.task'],
)

# Celery configuration
celery.conf.update(
    # Task routing
    task_routes={
        'tasks.task.process_outbox_events': {'queue': 'outbox'},
        'tasks.task.publish_single_event': {'queue': 'events'},
    },
    broker_connection_retry_on_startup=True,
    # Task execution
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    worker_pool="solo",
    
    # Worker configuration
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    
    # Beat schedule for periodic tasks
    beat_schedule={
        'process-outbox-events': {
            'task': 'tasks.task.process_outbox_events',
            'schedule': 10.0,  # Run every 10 seconds
            'options': {'queue': 'outbox'}
        },
    },
    
    # Result backend settings
    result_expires=3600,
    result_backend_transport_options={'master_name': 'mymaster'},
    
    # Broker settings
    broker_transport_options={'visibility_timeout': 3600},
    
    # Task settings
    task_acks_late=True,
    worker_disable_rate_limits=True,
)


# Patch asyncio for Celery
@worker_process_init.connect
def init_worker(**kwargs):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)