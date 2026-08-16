from app.services.dm_client import SendResult
from app.services.dm_worker import DMWorker, RollingWindowLimiter
from app.services.reconciler import Reconciler
from app.database import SessionLocal
from app.models import OutboundDM, Rule, utcnow


class FakeClient:
    def __init__(self, send_result: SendResult, get_status: str = "delivered"):
        self.send_result = send_result
        self.get_status = get_status
        self.send_calls = 0

    async def send_dm(self, recipient_user_id, message, comment_id, idempotency_key):
        self.send_calls += 1
        return self.send_result

    async def get_dm(self, dm_id):
        return {"dm_id": dm_id, "status": self.get_status}


async def _seed_pending():
    async with SessionLocal() as session:
        rule = Rule(keyword="PRICE", keyword_normalized="price", dm_message="hi")
        session.add(rule)
        await session.flush()
        dm = OutboundDM(
            rule_id=rule.rule_id,
            recipient_user_id="usr_1",
            comment_id="cmt_1",
            message="hi",
            idempotency_key=f"{rule.rule_id}:usr_1:1",
            status="pending",
            attempts=0,
            next_retry_at=utcnow(),
        )
        session.add(dm)
        await session.commit()
        return dm.id


async def test_worker_marks_queued_on_202(client):
    outbound_id = await _seed_pending()
    fake = FakeClient(SendResult(ok=True, status_code=202, dm_id="dm_abc", api_status="queued"))
    worker = DMWorker(fake, limiter=RollingWindowLimiter(limit=50))
    claimed = await worker.claim_one()
    assert claimed == outbound_id
    await worker.process_claimed(claimed)
    async with SessionLocal() as session:
        row = await session.get(OutboundDM, outbound_id)
        assert row.status == "queued"
        assert row.dm_id == "dm_abc"


async def test_worker_fails_on_400(client):
    outbound_id = await _seed_pending()
    fake = FakeClient(SendResult(ok=False, status_code=400, error="invalid_request", retryable=False))
    worker = DMWorker(fake, limiter=RollingWindowLimiter(limit=50))
    claimed = await worker.claim_one()
    await worker.process_claimed(claimed)
    async with SessionLocal() as session:
        row = await session.get(OutboundDM, outbound_id)
        assert row.status == "failed"


async def test_reconciler_marks_delivered(client):
    outbound_id = await _seed_pending()
    async with SessionLocal() as session:
        row = await session.get(OutboundDM, outbound_id)
        row.status = "queued"
        row.dm_id = "dm_xyz"
        await session.commit()
    fake = FakeClient(SendResult(ok=True, status_code=202, dm_id="dm_xyz"), get_status="delivered")
    await Reconciler(fake).tick()
    async with SessionLocal() as session:
        row = await session.get(OutboundDM, outbound_id)
        assert row.status == "delivered"
