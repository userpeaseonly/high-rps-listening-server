from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.future import select

import config

DATABASE_URL = config.DATABASE_URL

engine = create_async_engine(
    DATABASE_URL,
    echo=False if config.APP_ENV == "prod" else True,
    pool_size=20,
    max_overflow=30,
    pool_recycle=3600,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    __abstract__ = True

    def __repr__(self):
        return f"<{self.__class__.__name__} id={self.id}>"

    def to_dict(self):
        return {column.name: getattr(self, column.name) for column in self.__table__.columns}

    def __str__(self):
        return f"{self.__class__.__name__}(id={self.id})"


async def get_async_db():
    async with AsyncSessionLocal() as session:
        yield session



async def create_db_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _test_db_connection():
    """Test database connectivity"""
    async with AsyncSessionLocal() as db:
        await db.execute(select(1))