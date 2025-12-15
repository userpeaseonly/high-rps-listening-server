-- Migration: Add idempotency constraint to events table
-- This prevents duplicate events from being stored
-- Run this BEFORE deploying the new code version

-- Step 1: Create index for better lookup performance (if not exists)
CREATE INDEX IF NOT EXISTS idx_event_lookup ON events (device_id, serial_no, date_time);

-- Step 2: Add unique constraint to prevent duplicates
-- Note: This will fail if there are existing duplicates
-- In that case, clean up duplicates first before running this
ALTER TABLE events 
ADD CONSTRAINT uq_event_device_serial_time 
UNIQUE (device_id, serial_no, date_time);

-- If the above fails due to existing duplicates, run this first to identify them:
-- SELECT device_id, serial_no, date_time, COUNT(*) 
-- FROM events 
-- WHERE serial_no IS NOT NULL
-- GROUP BY device_id, serial_no, date_time 
-- HAVING COUNT(*) > 1;

-- Then delete duplicates keeping the oldest one:
-- DELETE FROM events 
-- WHERE id NOT IN (
--     SELECT MIN(id) 
--     FROM events 
--     WHERE serial_no IS NOT NULL
--     GROUP BY device_id, serial_no, date_time
-- );
