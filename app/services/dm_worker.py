import asyncio
import logging
from collections import deque
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text, update

from app.config import settings
from app.database import SessionLocal, engine
from app.models import DeletedComment, OutboundDM, utcnow
from app.services.dm_client import PseudoGramClient

logger = logging.getLogger(__name__)


class RollingWindowLimiter:
    """At most `limit` send calls in any rolling 60-second window."""

    def __init__(self, limit: int, window_seconds: float = 60.0):
        self.limit = limit
        self.window_seconds = window_seconds
        self._times: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                now = asyncio.get_event_loop().time()
                cutoff = now - self.window_seconds
                while self._times and self._times[0] <= cutoff:
                    self._times.popleft()
                if len(self._times) < self.limit:
                    self._times.append(now)
                    return
                wait = self._times[0] + self.window_seconds - now
            await asyncio.sleep(max(wait, 0.05))


def backoff_seconds(attempts: int) -> float:
    return min(60.0, 2.0 ** max(attempts, 1))


class DMWorker:
    def __init__(self, client: PseudoGramClient, limiter: RollingWindowLimiter | None = None):
        self.client = client
        self.limiter = limiter or RollingWindowLimiter(settings.rate_limit_per_minute)
        self._stopped = asyncio.Event()

    def stop(self) -> None:
        self._stopped.set()

    async def run(self) -> None:
        await self.reset_stale_claims()
        while not self._stopped.is_set():
            claimed = await self.claim_one()
            if claimed is None:
                try:
                    await asyncio.wait_for(self._stopped.wait(), timeout=settings.send_poll_seconds)
                except asyncio.TimeoutError:
                    continue
                break
            await self.process_claimed(claimed)

    async def reset_stale_claims(self) -> None:
        cutoff = utcnow() - timedelta(minutes=2)
        async with SessionLocal() as session:
            await session.execute(
                update(OutboundDM)
                .where(OutboundDM.status == "sending", OutboundDM.claimed_at < cutoff)
                .values(status="pending", claimed_at=None, updated_at=utcnow())
            )
            await session.commit()

    async def claim_one(self) -> str | None:
        now = utcnow()
        async with SessionLocal() as session:
            if engine.dialect.name == "postgresql":
                result = await session.execute(
                    text(
                        """
                        UPDATE outbound_dms
                        SET status = 'sending', claimed_at = :now, updated_at = :now
                        WHERE id = (
                            SELECT id FROM outbound_dms
                            WHERE status = 'pending'
                              AND (next_retry_at IS NULL OR next_retry_at <= :now)
                            ORDER BY created_at
                            FOR UPDATE SKIP LOCKED
                            LIMIT 1
                        )
                        RETURNING id
                        """
                    ),
                    {"now": now},
                )
                row = result.first()
                await session.commit()
                return row[0] if row else None

            row = (
                await session.execute(
                    select(OutboundDM)
                    .where(
                        OutboundDM.status == "pending",
                        (OutboundDM.next_retry_at.is_(None) | (OutboundDM.next_retry_at <= now)),
                    )
                    .order_by(OutboundDM.created_at)
                    .limit(1)
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            row.status = "sending"
            row.claimed_at = now
            row.updated_at = now
            dm_id = row.id
            await session.commit()
            return dm_id

    async def process_claimed(self, outbound_id: str) -> None:
        async with SessionLocal() as session:
            dm = await session.get(OutboundDM, outbound_id)
            if dm is None or dm.status != "sending":
                return
            deleted = await session.get(DeletedComment, dm.comment_id)
            if deleted is not None:
                await session.delete(dm)
                await session.commit()
                return

            recipient = dm.recipient_user_id
            message = dm.message
            comment_id = dm.comment_id
            idempotency_key = dm.idempotency_key
            attempts = dm.attempts

        await self.limiter.acquire()
        result = await self.client.send_dm(recipient, message, comment_id, idempotency_key)

        async with SessionLocal() as session:
            dm = await session.get(OutboundDM, outbound_id)
            if dm is None:
                return
            dm.attempts = attempts + 1
            dm.updated_at = utcnow()
            dm.claimed_at = None
            if result.ok and result.dm_id:
                dm.dm_id = result.dm_id
                dm.status = "queued"
                dm.last_error = None
            elif not result.retryable:
                dm.status = "failed"
                dm.last_error = result.error
            elif dm.attempts >= settings.max_send_attempts:
                dm.status = "failed"
                dm.last_error = result.error or "max_attempts"
            else:
                wait = result.retry_after if result.retry_after is not None else backoff_seconds(dm.attempts)
                dm.status = "pending"
                dm.next_retry_at = utcnow() + timedelta(seconds=wait)
                dm.last_error = result.error
            await session.commit()
