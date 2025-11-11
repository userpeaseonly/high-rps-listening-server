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
