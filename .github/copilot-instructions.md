# Event Listener Service - AI Agent Instructions

## Architecture Overview

This is a high-performance event listener service for the time-pay ecosystem that processes access control events from Hikvision devices. Built with **Robyn** (async Python web framework) + **Celery** + **Kafka**, using the **Transactional Outbox pattern** for reliable event publishing.

### Core Components
- **Robyn API** (`app.py`): High-concurrency HTTP server receiving events from devices
- **Outbox Pattern** (`outbox/`): Transactional event storage before Kafka publishing
- **Celery Workers** (`tasks/`): Background processors for outbox → Kafka relay
- **Kafka Producer** (`producer.py`): Reliable message publishing with retries & idempotence
- **PostgreSQL**: Dual storage for events (`events` table) and outbox (`outbox_events` table)

### Data Flow
1. Device POST → `/hik/events` with multipart form data (JSON + optional image)
2. Extract JSON from form data → Validate with Pydantic (`EventNotificationAlert` or `HeartbeatInfo`)
3. Save to `events` table + insert into `outbox_events` (single transaction)
4. Fire-and-forget: `asyncio.create_task(_publish_event_by_id())` for immediate publish attempt
5. Celery Beat runs `process_outbox_events` every 10s to catch any failed publishes

## Critical Patterns

### Event Processing Pattern
**Location**: `events/hik/events.py`
```python
# Events are discriminated by event_type field
event = TypeAdapter(EventUnion).validate_python(event_data)
if isinstance(event, HeartbeatInfo):
    # Currently SKIPPED (commented out) - no DB save, no Kafka publish
elif isinstance(event, EventNotificationAlert):
    # Only ATTENDANCE events get published to Kafka
    if event_in.purpose == models.PersonPurpose.ATTENDANCE:
        await add_to_outbox(db, str(saved_event.id), "Event", "access_control.event_created", ...)
```

**Key**: `PersonPurpose.ATTENDANCE` is determined by presence of `person_name` in the payload. Events without names are marked `PersonPurpose.INFORMATION` and NOT published.

### Outbox Pattern Implementation
**Reliability guarantee**: All Kafka publishes go through `outbox_events` table first
```python
# Dual approach for maximum reliability:
# 1. Immediate attempt (non-blocking)
asyncio.create_task(_publish_event_by_id(outbox_event.id))

# 2. Celery Beat fallback (every 10s) via process_outbox_events task
# Celery processes unprocessed events: WHERE processed = False
```

### Database Sessions
- **Async operations**: Use `AsyncSessionLocal()` context manager (SQLAlchemy 2.0 async)
- **Celery tasks**: Use sync event loop pattern (`get_event_loop().run_until_complete()`)
- **Connection pooling**: 20 base + 30 overflow with 1h recycle time

### Robyn Dependency Injection
**Location**: `events/hik/events.py`
```python
router.inject(EXTRACT_EVENT_DATA=extract_event_data)

@router.post("/events")
async def receive_event(request: Request, router_dependencies):
    _extract_event_data = router_dependencies['EXTRACT_EVENT_DATA']
```
Use `router.inject()` for testable dependencies, access via `router_dependencies` dict in handlers.

### Form Data Extraction
**Critical**: Events arrive as multipart with JSON embedded in form fields
```python
# Pattern in events/dependencies.py
json_string = next(
    (value for key, value in request.form_data.items() 
     if not isinstance(value, bytearray) and "eventType" in str(value)),
    None
)
```
Images arrive in `request.files` with dynamic keys (extract via `list(request.files.keys())[0]`).

## Development Commands

### Local Development
```bash
# Start dependencies
docker-compose up db redis -d

# Run Robyn server (auto-reload)
python app.py --processes=1 --workers=4

# Run Celery worker
celery -A celery_config worker --loglevel=info --concurrency=2 -E

# Run Celery Beat (periodic tasks)
celery -A celery_config beat --loglevel=info
```

### Production Deployment
```bash
# Full stack with Docker Compose
docker-compose up --build

# Services:
# - web: Robyn on port 8080 (ulimit 65536 for high RPS)
# - celery-worker: Background processor (concurrency=2)
# - celery-beat: Task scheduler
# - db: PostgreSQL on port 4123
# - redis: Redis on port 6379
```

### Database Migrations
```bash
# Tables auto-created on startup via handlers.create_all_tables
# Triggered by: app.startup_handler(handlers.create_all_tables)
```

## Configuration

**Environment Variables** (`.env` file):
```bash
DATABASE_URL=postgresql+asyncpg://user:pass@host/dbname
REDIS_URL=redis://localhost:6379/0
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
DEFAULT_KAFKA_TOPIC=attendance_records
DEFAULT_CLIENT_ID=time-pay-event-producer
APP_ENV=dev|prod|test  # Controls SQLAlchemy echo
TIME_ZONE=Asia/Tashkent
```

## Key Models & Schemas

### Database Models (`events/models.py`, `outbox/models.py`)
- `Event`: Main event storage with 20+ fields (person_id, card_no, attendance_status, etc.)
- `Heartbeat`: Device health checks (currently not saved)
- `OutboxEvent`: Transactional outbox (aggregate_id, event_type, payload JSONB, processed bool)

### Pydantic Schemas (`events/schemas/`)
- `EventNotificationAlert`: Access control events with nested `AccessControllerEvent`
- `HeartbeatInfo`: Device heartbeat signals
- `EventUnion = HeartbeatInfo | EventNotificationAlert` (discriminated by `event_type` field)

### Enums
- `PersonPurpose`: `ATTENDANCE = "att"` | `INFORMATION = "info"`
- `MessagePriority`: `LOW | NORMAL | HIGH | CRITICAL` (Kafka publishing priority)

## Testing & Debugging

### Health Checks
```bash
# Web health
curl http://localhost:8080/health

# Celery health (tests DB + Celery connectivity)
curl http://localhost:8080/health/celery
```

### Common Issues
1. **Events not publishing to Kafka**: Check `outbox_events.processed = false` rows
2. **Celery not processing**: Verify Redis connection + check Celery Beat scheduler is running
3. **Form data parsing errors**: Ensure `eventType` field exists in JSON payload
4. **Image saving**: Picture extraction logic present but saving not implemented (TODO)

## Adding New Event Types

1. Define Pydantic schema in `events/schemas/` with `alias` for camelCase fields
2. Add to `EventUnion` discriminated union
3. Handle in `events/hik/events.py` router with `isinstance()` check
4. Create corresponding database model in `events/models.py`
5. Add CRUD operations in `events/crud.py`
6. Update outbox publishing logic if Kafka publish needed

## Performance Tuning

- **Robyn workers**: Default 4 workers × 1 process (adjust via `--workers` flag)
- **Celery concurrency**: Default 2 (increase for higher outbox throughput)
- **Kafka batch settings**: See `producer.py` `ProducerConfig` (compression=gzip, acks=all)
- **DB connection pool**: 20 + 30 overflow (tune in `db.py` if needed)
- **Outbox batch size**: 100 events per Celery task (modify in `tasks/repository.py`)

## Logging

All modules use `logging.getLogger(__name__)`. Key log points:
- Event reception: `events/hik/events.py` logs pretty-printed events via `utils.log_pretty_event()`
- Outbox processing: `tasks/repository.py` logs batch stats (processed/failed counts)
- Kafka publishing: `producer.py` logs send success/failures with metadata
