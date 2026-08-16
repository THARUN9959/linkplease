import asyncio
import logging

from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.models import OutboundDM, utcnow

logger = logging.getLogger(__name__)


class Reconciler:
    def __init__(self, client):
        self.client = client
        self._stopped = asyncio.Event()

    def stop(self) -> None:
        self._stopped.set()

    async def run(self) -> None:
        while not self._stopped.is_set():
            await self.tick()
            try:
                await asyncio.wait_for(self._stopped.wait(), timeout=settings.reconcile_poll_seconds)
            except asyncio.TimeoutError:
                continue
            break

    async def tick(self) -> None:
        async with SessionLocal() as session:
            rows = (
                await session.execute(
                    select(OutboundDM).where(
                        OutboundDM.status == "queued",
                        OutboundDM.dm_id.is_not(None),
                    )
                )
            ).scalars().all()
            snapshots = [(row.id, row.dm_id, row.attempts, row.rule_id, row.recipient_user_id) for row in rows]

        for outbound_id, dm_id, attempts, rule_id, user_id in snapshots:
            status_body = await self.client.get_dm(dm_id)
            if not status_body:
                continue
            api_status = status_body.get("status")
            async with SessionLocal() as session:
                row = await session.get(OutboundDM, outbound_id)
                if row is None or row.status != "queued":
                    continue
                if api_status == "delivered":
                    row.status = "delivered"
                    row.updated_at = utcnow()
                    row.last_error = None
                elif api_status == "failed":
                    if attempts + 1 >= settings.max_send_attempts:
                        row.status = "failed"
                        row.last_error = "delivery_failed"
                        row.updated_at = utcnow()
                    else:
                        next_attempt = attempts + 1
                        row.status = "pending"
                        row.dm_id = None
                        row.attempts = next_attempt
                        row.idempotency_key = f"{rule_id}:{user_id}:{next_attempt + 1}"
                        row.next_retry_at = utcnow()
                        row.last_error = "delivery_failed_retry"
                        row.updated_at = utcnow()
                await session.commit()
