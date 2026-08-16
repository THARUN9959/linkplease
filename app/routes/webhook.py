import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.database import SessionLocal
from app.models import WebhookEvent
from app.services.signature import verify_signature

router = APIRouter()


@router.post("/webhook")
async def webhook(request: Request) -> Response:
    body = await request.body()
    if settings.verify_signatures:
        header = request.headers.get("X-PseudoGram-Signature")
        if not verify_signature(body, header, settings.pseudogram_api_key):
            raise HTTPException(status_code=401, detail="invalid signature")

    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="invalid json")

    event_id = payload.get("event_id")
    event_type = payload.get("event_type")
    if not event_id or not event_type:
        raise HTTPException(status_code=400, detail="missing event_id or event_type")

    is_new = await persist_event(event_id, event_type, payload)
    if is_new:
        request.app.state.spawn_processing(event_id)
    return Response(content="{}", media_type="application/json", status_code=200)


async def persist_event(event_id: str, event_type: str, payload: dict) -> bool:
    async with SessionLocal() as session:
        if await session.get(WebhookEvent, event_id) is not None:
            return False
        session.add(
            WebhookEvent(
                event_id=event_id,
                event_type=event_type,
                payload=payload,
                received_at=datetime.now(timezone.utc),
            )
        )
        try:
            await session.commit()
            return True
        except IntegrityError:
            await session.rollback()
            return False
