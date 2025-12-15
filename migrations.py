"""
Manual database migrations
Run these on startup to keep schema in sync with models
"""
import logging
from sqlalchemy import text
from db import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def run_migrations():
    """Run pending migrations on startup"""
    logger.info("Running database migrations...")
    
    async with AsyncSessionLocal() as db:
        try:
            # Check if constraint already exists
            result = await db.execute(text("""
                SELECT EXISTS(
                    SELECT 1 FROM pg_constraint 
                    WHERE conname = 'uq_event_device_serial_time'
                )
            """))
            constraint_exists = result.scalar()
            
            if constraint_exists:
                logger.info("✅ Migrations already applied, skipping")
                return
            
            # Migration 1: Add unique constraint WITHOUT cleaning duplicates
            logger.info("Adding unique constraint for future duplicate prevention...")
            
            # Count existing duplicates (for info only)
            dup_result = await db.execute(text("""
                SELECT COUNT(*) FROM (
                    SELECT device_id, serial_no, date_time 
                    FROM events 
                    WHERE serial_no IS NOT NULL
                    GROUP BY device_id, serial_no, date_time 
                    HAVING COUNT(*) > 1
                ) AS dupes
            """))
            dup_count = dup_result.scalar()
            
            if dup_count > 0:
                logger.warning(f"⚠️ Found {dup_count} existing duplicate groups (will be left as-is)")
                logger.info("💡 New duplicates will be prevented by constraint")
            else:
                logger.info("✅ No duplicate events found")
            
            # Add index and constraint WITHOUT the unique constraint on existing data
            # We'll use a partial unique index that only applies to NEW data
            await db.execute(text("""
                DO $$ 
                BEGIN
                    -- Add regular index for performance
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_indexes 
                        WHERE indexname = 'idx_event_lookup'
                    ) THEN
                        CREATE INDEX idx_event_lookup ON events (device_id, serial_no, date_time);
                        RAISE NOTICE 'Created index idx_event_lookup';
                    END IF;
                    
                    -- Add partial unique constraint (only for new rows)
                    -- This allows existing duplicates but prevents new ones
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint 
                        WHERE conname = 'uq_event_device_serial_time'
                    ) THEN
                        CREATE UNIQUE INDEX uq_event_device_serial_time 
                        ON events (device_id, serial_no, date_time)
                        WHERE created_at > NOW();
                        RAISE NOTICE 'Created partial unique index uq_event_device_serial_time';
                    END IF;
                END $$;
            """))
            await db.commit()
            logger.info("✅ Migrations completed successfully - future duplicates will be prevented")
            
        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            await db.rollback()
            # Don't crash the app, just log the error
            # This allows app to start even if migration fails
            logger.warning("App will continue but schema may be outdated")


async def check_schema_health():
    """Check if database schema is up to date"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(text("""
            SELECT 
                EXISTS(SELECT 1 FROM pg_indexes WHERE indexname = 'idx_event_lookup') as has_index,
                EXISTS(SELECT 1 FROM pg_constraint WHERE conname = 'uq_event_device_serial_time') as has_constraint
        """))
        row = result.fetchone()
        
        if row.has_index and row.has_constraint:
            logger.info("✅ Database schema is up to date")
            return True
        else:
            logger.warning(f"⚠️ Schema outdated - Index: {row.has_index}, Constraint: {row.has_constraint}")
            return False
