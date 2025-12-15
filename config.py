import os
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

load_dotenv()

APP_ENV = os.environ.get('APP_ENV', 'dev')

TEST_DATABASE_URL = os.environ.get('TEST_DATABASE_URL', '')

DATABASE_URL = os.environ.get('DATABASE_URL')


if APP_ENV == 'test':
    DATABASE_URL = TEST_DATABASE_URL

LANGUAGE_CODE = 'en'
TIME_ZONE = 'Asia/Tashkent'

# USE_TZ = True
USE_I18N = True
tz = ZoneInfo(TIME_ZONE)


# Redis URL for Celery broker and result backend
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')


# Kafka
KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')

DEFAULT_KAFKA_TOPIC = os.getenv('DEFAULT_KAFKA_TOPIC', 'attendance_records')

DEFAULT_CLIENT_ID = os.getenv('DEFAULT_CLIENT_ID', 'time-pay-event-producer')

# Outbox configuration
OUTBOX_RETENTION_HOURS = int(os.getenv('OUTBOX_RETENTION_HOURS', '24'))  # Keep processed events for 24 hours
OUTBOX_CLEANUP_INTERVAL = float(os.getenv('OUTBOX_CLEANUP_INTERVAL', '3600'))  # Cleanup every hour
OUTBOX_BATCH_SIZE = int(os.getenv('OUTBOX_BATCH_SIZE', '100'))  # Process 100 events per batch


