import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["START_BACKGROUND_WORKERS"] = "false"
os.environ["PSEUDOGRAM_API_KEY"] = "test-secret"
os.environ["VERIFY_SIGNATURES"] = "true"
os.environ["RATE_LIMIT_PER_MINUTE"] = "100"

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client():
    from app.database import engine
    from app.main import app
    from app.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    # Tests call process_event_id explicitly for deterministic assertions.
    app.state.spawn_processing = lambda _event_id: None
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
