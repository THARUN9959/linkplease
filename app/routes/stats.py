from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import DuplicateBlock, OutboundDM
from app.schemas import StatsResponse

router = APIRouter()

QUEUED_STATUSES = ("pending", "sending", "queued")


@router.get("/stats", response_model=StatsResponse)
async def get_stats(session: AsyncSession = Depends(get_session)) -> StatsResponse:
    sent = await _count_status(session, "delivered")
    failed = (
        await session.execute(
            select(func.count())
            .select_from(OutboundDM)
            .where(OutboundDM.status == "failed", OutboundDM.next_retry_at.is_(None))
        )
    ).scalar_one()
    queued = (
        await session.execute(
            select(func.count())
            .select_from(OutboundDM)
            .where(
                OutboundDM.status.in_(QUEUED_STATUSES)
                | ((OutboundDM.status == "failed") & OutboundDM.next_retry_at.is_not(None))
            )
        )
    ).scalar_one()
    duplicates_blocked = (
        await session.execute(select(func.count()).select_from(DuplicateBlock))
    ).scalar_one()
    return StatsResponse(
        sent=int(sent),
        failed=int(failed),
        queued=int(queued),
        duplicates_blocked=int(duplicates_blocked),
    )


async def _count_status(session: AsyncSession, status: str) -> int:
    result = await session.execute(
        select(func.count()).select_from(OutboundDM).where(OutboundDM.status == status)
    )
    return result.scalar_one()
