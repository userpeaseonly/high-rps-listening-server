# Production Deployment Checklist - Critical Fixes

## Changes Summary
This update fixes critical production issues while maintaining the fire-and-forget performance optimization.

### Fixed Issues:
1. ✅ Transaction safety violation (commit before fire-and-forget task)
2. ✅ Error handling for background tasks (prevents silent failures)
3. ✅ Producer singleton with health validation (handles connection failures)
4. ✅ Timezone inconsistencies (UTC everywhere)
5. ✅ Sanitized error responses (no internal detail leaks)
6. ✅ Outbox cleanup task (prevents unbounded table growth)
7. ✅ Database idempotency (prevents duplicate events)

## Pre-Deployment Steps

### 1. Database Migration (REQUIRED)
```bash
# Connect to production database
psql -h <host> -U <user> -d <database>

# Run the migration script
\i migrations/add_event_idempotency.sql

# Verify the constraint was added
\d events
```

**IMPORTANT**: If the migration fails due to existing duplicates, clean them up first:
```sql
-- Find duplicates
SELECT device_id, serial_no, date_time, COUNT(*) 
FROM events 
WHERE serial_no IS NOT NULL
GROUP BY device_id, serial_no, date_time 
HAVING COUNT(*) > 1;

-- Delete duplicates (keeps oldest)
DELETE FROM events 
WHERE id NOT IN (
    SELECT MIN(id) 
    FROM events 
    WHERE serial_no IS NOT NULL
    GROUP BY device_id, serial_no, date_time
);
```

### 2. Environment Variables (OPTIONAL)
Add these to your `.env` file for tuning:
```bash
# Outbox retention (default: 24 hours)
OUTBOX_RETENTION_HOURS=24

# Cleanup interval in seconds (default: 3600 = 1 hour)
OUTBOX_CLEANUP_INTERVAL=3600

# Outbox batch size (default: 100)
OUTBOX_BATCH_SIZE=100
```

### 3. Code Review Checklist
- [ ] Migration script tested on staging database
- [ ] No existing duplicate events in production
- [ ] Environment variables configured
- [ ] Celery Beat scheduler is running (for cleanup task)

## Deployment Process

### Standard Docker Compose Deployment
```bash
# Stop existing services
docker-compose down

# Pull latest code
git pull origin v2/kafka-producer

# Rebuild and start
docker-compose up --build -d

# Verify all services are running
docker-compose ps

# Check logs for errors
docker-compose logs -f web celery-worker celery-beat
```

### Rolling Deployment (Zero Downtime)
```bash
# 1. Start new version alongside old
docker-compose up -d --scale web=2 --no-recreate

# 2. Wait for health check
curl http://localhost:8080/health

# 3. Stop old version
docker-compose up -d --scale web=1

# 4. Update Celery workers
docker-compose restart celery-worker celery-beat
```

## Post-Deployment Verification

### 1. Health Checks
```bash
# Web service health
curl http://localhost:8080/health
# Expected: {"status": "ok"}

# Celery health
curl http://localhost:8080/health/celery
# Expected: {"celery_status": "ok", "details": {...}}
```

### 2. Monitor Logs
```bash
# Watch for errors in event processing
docker-compose logs -f web | grep -i error

# Verify outbox processing
docker-compose logs -f celery-worker | grep "Outbox batch complete"

# Check cleanup task (runs hourly)
docker-compose logs -f celery-beat | grep "cleanup"
```

### 3. Test Event Ingestion
```bash
# Send test event (adjust payload for your devices)
curl -X POST http://localhost:8080/hik/events \
  -F 'eventData={"eventType":"AccessControllerEvent","dateTime":"2025-12-15T12:00:00Z",...}'

# Verify event saved
docker-compose exec db psql -U <user> -d <database> -c \
  "SELECT COUNT(*) FROM events WHERE created_at > NOW() - INTERVAL '1 minute';"

# Verify outbox processing
docker-compose exec db psql -U <user> -d <database> -c \
  "SELECT processed, COUNT(*) FROM outbox_events GROUP BY processed;"
```

### 4. Test Duplicate Handling
```bash
# Send the same event twice
curl -X POST http://localhost:8080/hik/events \
  -F 'eventData={"eventType":"AccessControllerEvent","dateTime":"2025-12-15T12:00:00Z",...}'

# Second request should return: "Event already processed (duplicate)"
# No duplicate in database
```

## Rollback Plan

If critical issues occur:

```bash
# Quick rollback to previous version
docker-compose down
git checkout <previous-commit>
docker-compose up --build -d

# Revert database migration (if needed)
psql -h <host> -U <user> -d <database> -c \
  "ALTER TABLE events DROP CONSTRAINT IF EXISTS uq_event_device_serial_time;"
```

## Monitoring Recommendations

### Key Metrics to Watch:
1. **Event ingestion rate**: Monitor incoming requests/second
2. **Outbox processing lag**: Check unprocessed event count
   ```sql
   SELECT COUNT(*) FROM outbox_events WHERE processed = false;
   ```
3. **Duplicate rate**: Monitor "Event already processed" log entries
4. **Cleanup effectiveness**: Check outbox table size weekly
   ```sql
   SELECT COUNT(*), processed FROM outbox_events GROUP BY processed;
   ```

### Alert Thresholds:
- Unprocessed outbox events > 1000
- Processed outbox events > 100,000 (cleanup not running)
- Database connection failures > 5/minute
- Kafka publish failures > 10/minute

## Performance Impact

**Expected changes:**
- ✅ Same HTTP response time (fire-and-forget preserved)
- ✅ Slightly safer under high load (proper transaction handling)
- ✅ No memory leaks from asyncio tasks (error callbacks added)
- ✅ Disk space controlled (automatic cleanup)
- ✅ No duplicate data (idempotency enforced)

## Questions or Issues?

If you encounter problems:
1. Check logs: `docker-compose logs -f`
2. Verify database connectivity: `docker-compose exec web python -c "from db import _test_db_connection; import asyncio; asyncio.run(_test_db_connection())"`
3. Check Redis: `docker-compose exec redis redis-cli ping`
4. Verify Kafka: Check producer logs for connection errors

---
**Last Updated**: December 15, 2025
**Version**: v2 with critical fixes
