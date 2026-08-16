import asyncio
import json

from app.services.events import process_event_id
from app.services.signature import compute_signature

SECRET = "test-secret"


def signed_headers(body: bytes) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-PseudoGram-Signature": compute_signature(body, SECRET),
    }


def comment_event(event_id: str, comment_id: str, user_id: str, text: str) -> dict:
    return {
        "event_id": event_id,
        "event_type": "comment.created",
        "sent_at": "2026-08-10T09:14:22.481Z",
        "data": {
            "comment_id": comment_id,
            "post_id": "post_1",
            "text": text,
            "created_at": "2026-08-10T09:14:21.900Z",
            "from": {"user_id": user_id, "username": "someone"},
        },
    }


def deleted_event(event_id: str, comment_id: str) -> dict:
    return {
        "event_id": event_id,
        "event_type": "comment.deleted",
        "sent_at": "2026-08-10T09:14:22.481Z",
        "data": {"comment_id": comment_id},
    }


async def test_create_rule_and_stats_shape(client):
    response = await client.post("/rules", json={"keyword": "PRICE", "dm_message": "list"})
    assert response.status_code == 201
    body = response.json()
    assert body["keyword"] == "PRICE"
    assert body["dm_message"] == "list"
    assert "rule_id" in body

    stats = await client.get("/stats")
    assert stats.status_code == 200
    assert stats.json() == {"sent": 0, "failed": 0, "queued": 0, "duplicates_blocked": 0}


async def test_webhook_rejects_forged_signature(client):
    payload = comment_event("evt_x", "cmt_x", "usr_x", "PRICE")
    body = json.dumps(payload).encode()
    response = await client.post(
        "/webhook",
        content=body,
        headers={"Content-Type": "application/json", "X-PseudoGram-Signature": "sha256=deadbeef"},
    )
    assert response.status_code == 401


async def test_comment_enqueues_dm_and_blocks_duplicate_user(client):
    await client.post("/rules", json={"keyword": "PRICE", "dm_message": "Here's the price list"})

    first = comment_event("evt_1", "cmt_1", "usr_1", "PRICE please")
    body = json.dumps(first).encode()
    response = await client.post("/webhook", content=body, headers=signed_headers(body))
    assert response.status_code == 200
    await process_event_id("evt_1")

    stats = (await client.get("/stats")).json()
    assert stats["queued"] == 1
    assert stats["duplicates_blocked"] == 0

    second = comment_event("evt_2", "cmt_2", "usr_1", "PRICE again")
    body = json.dumps(second).encode()
    response = await client.post("/webhook", content=body, headers=signed_headers(body))
    assert response.status_code == 200
    await process_event_id("evt_2")

    stats = (await client.get("/stats")).json()
    assert stats["queued"] == 1
    assert stats["duplicates_blocked"] == 1


async def test_event_id_redelivery_does_not_double_enqueue(client):
    await client.post("/rules", json={"keyword": "PRICE", "dm_message": "list"})
    event = comment_event("evt_same", "cmt_9", "usr_9", "need PRICE")
    body = json.dumps(event).encode()
    headers = signed_headers(body)
    assert (await client.post("/webhook", content=body, headers=headers)).status_code == 200
    assert (await client.post("/webhook", content=body, headers=headers)).status_code == 200
    await process_event_id("evt_same")
    await asyncio.sleep(0)
    stats = (await client.get("/stats")).json()
    assert stats["queued"] == 1
    assert stats["duplicates_blocked"] == 0


async def test_deleted_before_created_skips_dm(client):
    await client.post("/rules", json={"keyword": "PRICE", "dm_message": "list"})
    deleted = deleted_event("evt_del", "cmt_gone")
    body = json.dumps(deleted).encode()
    await client.post("/webhook", content=body, headers=signed_headers(body))
    await process_event_id("evt_del")

    created = comment_event("evt_new", "cmt_gone", "usr_2", "PRICE")
    body = json.dumps(created).encode()
    await client.post("/webhook", content=body, headers=signed_headers(body))
    await process_event_id("evt_new")

    stats = (await client.get("/stats")).json()
    assert stats["queued"] == 0
    assert stats["sent"] == 0
    assert stats["failed"] == 0
