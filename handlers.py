import logging

from db import create_db_tables
from migrations import run_migrations

logger = logging.getLogger(__name__)

def startup_message():
    logger.info("Event Listener is starting up...")
    print("Event Listener is starting up...")


def shutdown_message():
    logger.info("Event Listener is shutting down...")
    print("Event Listener is shutting down...")

async def create_all_tables():
    # Create tables if they don't exist
    await create_db_tables()
    # Run migrations to update existing tables
    await run_migrations()
