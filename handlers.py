import logging

from db import create_db_tables
logger = logging.getLogger(__name__)

def startup_message():
    logger.info("Event Listener is starting up...")
    print("Event Listener is starting up...")


def shutdown_message():
    logger.info("Event Listener is shutting down...")
    print("Event Listener is shutting down...")

async def create_all_tables():
    await create_db_tables()
