from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import Rule
from app.schemas import RuleCreate, RuleResponse

router = APIRouter()


@router.post("/rules", status_code=201, response_model=RuleResponse)
async def create_rule(body: RuleCreate, session: AsyncSession = Depends(get_session)) -> RuleResponse:
    rule = Rule(
        keyword=body.keyword,
        keyword_normalized=body.keyword.lower(),
        dm_message=body.dm_message,
    )
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    return RuleResponse(rule_id=rule.rule_id, keyword=rule.keyword, dm_message=rule.dm_message)
