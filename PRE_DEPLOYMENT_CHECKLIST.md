# Pre-Production Deployment Checklist

## ✅ Code Quality Status: READY

### Critical Fixes Verified:
- ✅ Transaction safety: `db.commit()` before `asyncio.create_task()` 
- ✅ Error handling: Fire-and-forget tasks have error callbacks
- ✅ Timezone consistency: All `datetime.now(timezone.utc)` (no more `utcnow()`)
- ✅ Producer singleton: Health validation with thread-safe lock
- ✅ Error sanitization: No internal details leaked to clients
- ✅ Idempotency: Unique constraint on events + duplicate handling
- ✅ Cleanup task: Celery Beat scheduled for outbox retention

### Code Quality:
- ⚠️ 3 Sourcery style suggestions (non-critical, cosmetic only):
  1. Line 142 in events/hik/events.py - negation in if/else (works correctly)
  2. Line 86 in producer.py - f-string with no interpolation (harmless)
  3. Line 238 in producer.py - sum() optimization (micro-optimization)

**These are NOT bugs, just style suggestions. Code is functionally correct.**

---

## 🚨 MANDATORY STEPS BEFORE DEPLOYMENT:

### 1. Database Migration (CRITICAL - DO THIS FIRST)
```bash
# Backup production database first!
pg_dump -h <host> -U <user> -d <database> > backup_$(date +%Y%m%d_%H%M%S).sql

# Connect to production database
psql -h <host> -U <user> -d <database>

# Check for existing duplicates (MUST BE ZERO)
SELECT device_id, serial_no, date_time, COUNT(*) 
FROM events 
WHERE serial_no IS NOT NULL
GROUP BY device_id, serial_no, date_time 
HAVING COUNT(*) > 1;

# If duplicates exist, clean them up first:
DELETE FROM events 
WHERE id NOT IN (
    SELECT MIN(id) 
    FROM events 
    WHERE serial_no IS NOT NULL
    GROUP BY device_id, serial_no, date_time
);

# Run the migration
\i migrations/add_event_idempotency.sql

# Verify constraint was added
\d events
# Should show: "uq_event_device_serial_time" UNIQUE CONSTRAINT
```

### 2. Environment Variables
Add to `.env` (optional tuning):
```bash
# Outbox cleanup settings
OUTBOX_RETENTION_HOURS=24           # Keep processed events for 24 hours
OUTBOX_CLEANUP_INTERVAL=3600        # Cleanup every hour (3600 seconds)
OUTBOX_BATCH_SIZE=100               # Process 100 events per batch
```

### 3. Verify Prerequisites
```bash
# Check PostgreSQL version (needs 12+)
psql --version

# Verify Redis is accessible
redis-cli -h <redis_host> ping

# Verify Kafka is accessible
kafka-topics.sh --bootstrap-server <kafka_host>:9092 --list

# Verify Docker Compose version (needs 2.0+)
docker-compose --version
```

---

## 📋 DEPLOYMENT PROCEDURE:

### Option A: Standard Deployment (Brief Downtime)
```bash
# 1. Stop current services
docker-compose down

# 2. Pull latest code
git pull origin v2/kafka-producer

# 3. Rebuild images
docker-compose build

# 4. Start services
docker-compose up -d

# 5. Monitor startup
docker-compose logs -f web celery-worker celery-beat

# Wait for "Kafka Producer Service started successfully!"
```

### Option B: Zero-Downtime Rolling Deployment
```bash
# 1. Scale up web service
docker-compose up -d --scale web=2 --no-recreate

# 2. Wait for health check
sleep 10
curl http://localhost:8080/health
# Should return: {"status": "ok"}

# 3. Scale down to new version only
docker-compose stop <old_web_container_id>
docker-compose up -d --scale web=1

# 4. Update workers
docker-compose restart celery-worker celery-beat
```

---

## ✅ POST-DEPLOYMENT VERIFICATION:

### 1. Health Checks (MANDATORY)
```bash
# Web service
curl http://localhost:8080/health
# Expected: {"status": "ok"}

# Celery connectivity
curl http://localhost:8080/health/celery
# Expected: {"celery_status": "ok", ...}
```

### 2. Test Event Ingestion
```bash
# Send a test event from a real device
# OR use curl (adjust payload for your setup):
curl -X POST http://localhost:8080/hik/events \
  -H "Content-Type: multipart/form-data" \
  -F 'eventData={"eventType":"AccessControllerEvent",...}'

# Response should be 200 OK
```

### 3. Verify Database
```bash
docker-compose exec db psql -U <user> -d <database> -c \
  "SELECT COUNT(*) FROM events WHERE created_at > NOW() - INTERVAL '5 minutes';"
# Should show your test event

docker-compose exec db psql -U <user> -d <database> -c \
  "SELECT processed, COUNT(*) FROM outbox_events GROUP BY processed;"
# Should show processed=true for published events
```

### 4. Test Idempotency
```bash
# Send the SAME event twice (same device_id, serial_no, date_time)
# First: Should return "Event processed successfully"
# Second: Should return "Event already processed (duplicate)"

# Verify only ONE event in database
docker-compose exec db psql -U <user> -d <database> -c \
  "SELECT COUNT(*) FROM events WHERE device_id = '<test_device>' AND serial_no = <test_serial>;"
# Should be 1, not 2
```

### 5. Monitor Logs (First 30 Minutes)
```bash
# Watch for errors
docker-compose logs -f web | grep -E "ERROR|WARNING"

# Verify outbox processing
docker-compose logs -f celery-worker | grep "Outbox batch complete"

# Check Kafka publishing
docker-compose logs -f web | grep "Successfully published"

# Watch cleanup task (runs hourly)
docker-compose logs -f celery-beat | grep "cleanup"
```

---

## 🔍 EXPECTED BEHAVIOR:

### Normal Operation:
1. Device sends event → 200 OK response in <100ms
2. Event saved to DB + outbox table
3. Fire-and-forget task attempts immediate Kafka publish
4. Celery Beat processes any failed events every 10 seconds
5. Cleanup task runs every hour to delete old processed events

### Duplicate Event:
1. Device sends duplicate → 200 OK "Event already processed (duplicate)"
2. No new DB entry
3. No new Kafka message
4. Log warning about duplicate

### Kafka Failure:
1. Event saved to DB + outbox
2. Fire-and-forget fails → logged as error
3. Celery Beat will retry in next batch (10 seconds)
4. No HTTP error to device (outbox ensures delivery)

---

## ⚠️ MONITORING ALERTS TO SET UP:

### Critical:
- Unprocessed outbox events > 1000 for > 5 minutes
- Database connection failures > 5/minute
- Kafka producer not running (health check fails)

### Warning:
- Duplicate events > 10% of total events
- Outbox table size > 100,000 rows (cleanup not running)
- Fire-and-forget failures > 20/minute

### Metrics to Track:
```bash
# Check unprocessed outbox count
SELECT COUNT(*) FROM outbox_events WHERE processed = false;

# Check outbox table size
SELECT 
  processed, 
  COUNT(*), 
  MIN(created_at) as oldest,
  MAX(created_at) as newest 
FROM outbox_events 
GROUP BY processed;

# Check duplicate rate
grep "Duplicate event" /var/log/app.log | wc -l
```

---

## 🔙 ROLLBACK PLAN (If Issues Occur):

### Quick Rollback:
```bash
# 1. Rollback code
docker-compose down
git revert HEAD
docker-compose up --build -d

# 2. Remove database constraint (if causing issues)
psql -h <host> -U <user> -d <database> -c \
  "ALTER TABLE events DROP CONSTRAINT IF EXISTS uq_event_device_serial_time;"
```

### Symptoms Requiring Rollback:
- ❌ Events failing to save (not duplicate-related)
- ❌ Response times > 500ms consistently
- ❌ Kafka messages not being published at all
- ❌ Database errors on every request

### Symptoms NOT Requiring Rollback:
- ✅ Occasional "Duplicate event" warnings (expected)
- ✅ Individual fire-and-forget errors (Celery will retry)
- ✅ Kafka temporarily down (outbox will buffer)

---

## 📊 SUCCESS CRITERIA:

After 1 hour of production use:
- [ ] All events from devices are being saved
- [ ] Duplicate events are being rejected correctly
- [ ] Outbox processing is working (check processed=true count)
- [ ] No critical errors in logs
- [ ] Response times < 100ms average
- [ ] Kafka messages are being published

---

## ❓ TROUBLESHOOTING:

### "Events not saving"
```bash
# Check database connectivity
docker-compose exec web python -c "from db import _test_db_connection; import asyncio; asyncio.run(_test_db_connection())"

# Check logs for DB errors
docker-compose logs web | grep -i "database\|postgres"
```

### "Outbox not processing"
```bash
# Check Celery Beat is running
docker-compose ps celery-beat

# Check Celery worker logs
docker-compose logs celery-worker | grep "process_outbox_events"

# Manually trigger processing
docker-compose exec celery-worker celery -A celery_config call tasks.task.process_outbox_events
```

### "Kafka not publishing"
```bash
# Check producer health
docker-compose exec web python -c "from producer import get_producer_service; import asyncio; p = asyncio.run(get_producer_service()); print(p.is_running)"

# Check Kafka connectivity
docker-compose exec web python -c "import socket; socket.create_connection(('kafka_host', 9092))"
```

---

## 🎯 FINAL CHECKLIST:

Before going live:
- [ ] Database backup completed
- [ ] Migration script executed successfully
- [ ] No duplicate events in production database
- [ ] Environment variables configured
- [ ] All services started successfully
- [ ] Health checks passing
- [ ] Test event processed successfully
- [ ] Duplicate test event rejected correctly
- [ ] Monitoring/alerting configured
- [ ] Team notified of deployment
- [ ] Rollback plan understood

---

**Status**: ✅ CODE IS PRODUCTION-READY
**Risk Level**: LOW (all critical issues fixed)
**Recommended Time**: During low-traffic period (optional, not critical)

**Estimated Deployment Time**: 15-30 minutes
**Estimated Downtime**: 0-2 minutes (depending on deployment method)
