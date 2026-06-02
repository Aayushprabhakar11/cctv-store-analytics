from collections.abc import AsyncGenerator

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, UniqueConstraint, create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

Base = declarative_base()


class EventRow(Base):
    __tablename__ = "events"
    __table_args__ = (UniqueConstraint("event_id", name="uq_event_id"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(36), nullable=False, index=True)
    store_id = Column(String(64), nullable=False, index=True)
    camera_id = Column(String(64), nullable=False)
    visitor_id = Column(String(64), nullable=False, index=True)
    event_type = Column(String(32), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    zone_id = Column(String(64), nullable=True)
    dwell_ms = Column(Integer, default=0)
    is_staff = Column(Integer, default=0)
    confidence = Column(Float, nullable=False)
    metadata_json = Column(Text, nullable=True)


class PosRow(Base):
    __tablename__ = "pos_transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(String(64), nullable=False, index=True)
    transaction_id = Column(String(64), nullable=False, unique=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    basket_value_inr = Column(Float, nullable=False)


def _sync_url() -> str:
    url = settings.database_url
    if url.startswith("sqlite+aiosqlite"):
        return url.replace("sqlite+aiosqlite", "sqlite")
    return url


engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
sync_engine = create_engine(_sync_url(), echo=False)
SyncSession = sessionmaker(sync_engine)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session


_db_available = True


def set_db_available(available: bool) -> None:
    global _db_available
    _db_available = available


def is_db_available() -> bool:
    return _db_available
