import logging
import handlers

from robyn import Robyn
from events.hik.events import router as hik_events_router
from tasks.task import health_check
from migrations import check_schema_health

logger = logging.getLogger(__name__)

app = Robyn(__file__)

app.startup_handler(handlers.create_all_tables)

app.include_router(hik_events_router)

@app.get("/health")
def index():
    return {"status": "ok"}

@app.get("/health/celery")
async def celery_health():
    """Health check endpoint to verify Celery connectivity"""
    try:
        result = health_check.delay()
        health_status = result.get(timeout=5)
        return {"celery_status": "ok", "details": health_status}
    except Exception as e:
        return {"celery_status": "error", "error": str(e)}

@app.get("/health/schema")
async def schema_health():
    """Health check endpoint to verify database schema is up to date"""
    try:
        is_healthy = await check_schema_health()
        return {"schema_status": "ok" if is_healthy else "outdated", "up_to_date": is_healthy}
    except Exception as e:
        return {"schema_status": "error", "error": str(e)}

if __name__ == "__main__":
    app.start(host="0.0.0.0", port=8080)
