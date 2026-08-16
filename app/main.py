import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.database import engine
from app.models import Base
from app.routes.rules import router as rules_router
from app.routes.stats import router as stats_router
from app.routes.webhook import router as webhook_router
from app.services.dm_client import PseudoGramClient
from app.services.dm_worker import DMWorker
from app.services.events import process_event_id, replay_unprocessed_events
from app.services.reconciler import Reconciler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    client = PseudoGramClient()
    worker = DMWorker(client)
    reconciler = Reconciler(client)
    tasks: list[asyncio.Task] = []

    def spawn_processing(event_id: str) -> None:
        tasks.append(asyncio.create_task(process_event_id(event_id)))

    app.state.client = client
    app.state.worker = worker
    app.state.reconciler = reconciler
    app.state.spawn_processing = spawn_processing

    if settings.start_background_workers:
        tasks.append(asyncio.create_task(worker.run()))
        tasks.append(asyncio.create_task(reconciler.run()))
        tasks.append(asyncio.create_task(replay_unprocessed_events()))

    yield

    worker.stop()
    reconciler.stop()
    for task in tasks:
        task.cancel()
    await client.aclose()


def create_app() -> FastAPI:
    application = FastAPI(title="LinkPlease", lifespan=lifespan)
    application.include_router(webhook_router)
    application.include_router(rules_router)
    application.include_router(stats_router)

    @application.get("/")
    async def root():
        return {
            "service": "LinkPlease",
            "status": "running",
            "routes": {
                "POST /rules": "Create keyword to DM rule",
                "POST /webhook": "Receive comment events",
                "GET /stats": "Live delivery metrics",
                "GET /health": "Health check",
                "GET /docs": "Interactive API docs",
            },
        }

    @application.get("/health")
    async def health():
        return {"ok": True}

    return application


app = create_app()
