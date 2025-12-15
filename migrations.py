"""
Manual database migrations
Run these on startup to keep schema in sync with models
"""
import logging
import os
from sqlalchemy import text
from db import AsyncSessionLocal

logger = logging.getLogger(__name__)

# Allow disabling migrations via env var (set RUN_MIGRATIONS=false to skip)
MIGRATIONS_ENABLED = os.getenv("RUN_MIGRATIONS", "true").lower() == "true"


async def run_migrations():
    """Run pending migrations on startup"""
    if not MIGRATIONS_ENABLED:
        logger.info("⏭️ Migrations disabled (RUN_MIGRATIONS=false)")
        return
    
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
            
            # Migration 1: Add unique constraint for future duplicates only
            logger.info("Adding constraint to prevent future duplicates (old data unchanged)...")
            
            # Add ONLY partial unique index for new rows (no full table index)
            # This takes seconds instead of hours
            await db.execute(text("""
                DO $$ 
                BEGIN
                    -- Add partial unique constraint (only for new rows)
                    -- This allows existing duplicates but prevents new ones
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_indexes 
                        WHERE indexname = 'uq_event_device_serial_time'
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
