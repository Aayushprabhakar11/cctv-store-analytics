import json
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.database import Base, get_session
from app.main import app

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TEST_DB = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(autouse=True)
def reset_app_state():
    from app.database import set_db_available

    set_db_available(True)
    app.dependency_overrides.clear()
    yield
    set_db_available(True)
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(TEST_DB, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_session():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    yield factory
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def sample_events():
    path = DATA_DIR / "sample_events.jsonl"
    events = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))
    return events


@pytest_asyncio.fixture
async def seeded_client(client, sample_events):
    r = await client.post("/events/ingest", json={"events": sample_events})
    assert r.status_code == 200
    return client
