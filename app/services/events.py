import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import engine
from app.models import DeletedComment, DuplicateBlock, OutboundDM, Rule, WebhookEvent, utcnow

_event_locks: dict[str, asyncio.Lock] = {}
_event_locks_guard = asyncio.Lock()
_user_rule_locks: dict[tuple[str, str], asyncio.Lock] = {}
_user_rule_locks_guard = asyncio.Lock()


def comment_matches_rule(text: str, keyword_normalized: str) -> bool:
    return keyword_normalized in (text or "").lower()


def dialect_insert(model):
    if engine.dialect.name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        return sqlite_insert(model)
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    return pg_insert(model)


async def process_event_id(event_id: str) -> None:
    from app.database import SessionLocal

    async with _event_locks_guard:
        lock = _event_locks.setdefault(event_id, asyncio.Lock())
    async with lock:
        async with SessionLocal() as session:
            event = await session.get(WebhookEvent, event_id)
            if event is None or event.processed_at is not None:
                return
            await process_event(session, event)
            await session.commit()


async def process_event(session: AsyncSession, event: WebhookEvent) -> None:
    if event.processed_at is not None:
        return
    data = (event.payload or {}).get("data") or {}
    if event.event_type == "comment.deleted":
        await handle_comment_deleted(session, data.get("comment_id"))
    elif event.event_type == "comment.created":
        await handle_comment_created(session, event.event_id, data)
    event.processed_at = utcnow()


async def handle_comment_deleted(session: AsyncSession, comment_id: str | None) -> None:
    if not comment_id:
        return
    stmt = (
        dialect_insert(DeletedComment)
        .values(comment_id=comment_id, deleted_at=utcnow())
        .on_conflict_do_nothing(index_elements=["comment_id"])
    )
    await session.execute(stmt)

    pending = await session.execute(
        select(OutboundDM).where(
            OutboundDM.comment_id == comment_id,
            OutboundDM.status.in_(("pending", "sending")),
        )
    )
    for dm in pending.scalars().all():
        await session.delete(dm)


async def handle_comment_created(session: AsyncSession, event_id: str, data: dict) -> None:
    comment_id = data.get("comment_id")
    text = data.get("text") or ""
    user_id = (data.get("from") or {}).get("user_id")
    if not comment_id or not user_id:
        return

    if await session.get(DeletedComment, comment_id) is not None:
        return

    rules = (await session.execute(select(Rule))).scalars().all()
    for rule in rules:
        if not comment_matches_rule(text, rule.keyword_normalized):
            continue
        await enqueue_or_block(session, rule, user_id, comment_id, event_id)


async def enqueue_or_block(
    session: AsyncSession,
    rule: Rule,
    user_id: str,
    comment_id: str,
    event_id: str,
) -> None:
    key = (rule.rule_id, user_id)
    async with _user_rule_locks_guard:
        lock = _user_rule_locks.setdefault(key, asyncio.Lock())
    async with lock:
        now = utcnow()
        stmt = (
            dialect_insert(OutboundDM)
            .values(
                id=str(uuid.uuid4()),
                rule_id=rule.rule_id,
                recipient_user_id=user_id,
                comment_id=comment_id,
                message=rule.dm_message,
                idempotency_key=f"{rule.rule_id}:{user_id}:1",
                status="pending",
                attempts=0,
                next_retry_at=now,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(index_elements=["rule_id", "recipient_user_id"])
            .returning(OutboundDM.id)
        )
        inserted = (await session.execute(stmt)).first()
        if inserted is None:
            session.add(
                DuplicateBlock(
                    rule_id=rule.rule_id,
                    recipient_user_id=user_id,
                    event_id=event_id,
                )
            )


async def replay_unprocessed_events() -> None:
    from app.database import SessionLocal

    async with SessionLocal() as session:
        rows = (
            await session.execute(select(WebhookEvent.event_id).where(WebhookEvent.processed_at.is_(None)))
        ).scalars().all()
    for event_id in rows:
        await process_event_id(event_id)
