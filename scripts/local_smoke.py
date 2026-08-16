"""Quick local end-to-end smoke test against http://127.0.0.1:8765."""

from __future__ import annotations

import json
import os
import sys
import time

import httpx

BASE = os.environ.get("APP_URL", "http://127.0.0.1:8765").rstrip("/")
API_KEY = os.environ.get("PSEUDOGRAM_API_KEY", "replace-me")


def sign(body: bytes) -> dict[str, str]:
    from app.services.signature import compute_signature

    return {
        "Content-Type": "application/json",
        "X-PseudoGram-Signature": compute_signature(body, API_KEY),
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
            "from": {"user_id": user_id, "username": "tester"},
        },
    }


def main() -> int:
    client = httpx.Client(base_url=BASE, timeout=10.0)
    suffix = str(int(time.time()))
    user_id = f"usr_smoke_{suffix}"

    print("1. Health")
    print("  ", client.get("/health").json())

    print("2. Create PRICE rule")
    rule = client.post("/rules", json={"keyword": "PRICE", "dm_message": "Here is the price list"}).json()
    print("  ", rule)

    print(f"3. Webhook: first comment from {user_id}")
    body = json.dumps(comment_event(f"evt_smoke_1_{suffix}", f"cmt_1_{suffix}", user_id, "PRICE please")).encode()
    r = client.post("/webhook", content=body, headers=sign(body))
    print("  ", r.status_code, r.text)

    print("4. Webhook: duplicate user, new comment")
    body = json.dumps(comment_event(f"evt_smoke_2_{suffix}", f"cmt_2_{suffix}", user_id, "send PRICE again")).encode()
    r = client.post("/webhook", content=body, headers=sign(body))
    print("  ", r.status_code, r.text)

    print("5. Webhook: redeliver same event_id")
    body = json.dumps(comment_event(f"evt_smoke_1_{suffix}", f"cmt_1_{suffix}", user_id, "PRICE please")).encode()
    r = client.post("/webhook", content=body, headers=sign(body))
    print("  ", r.status_code, r.text)

    print("6. Wait for background worker...")
    time.sleep(3)

    stats = client.get("/stats").json()
    print("7. Stats")
    print("  ", stats)

    client.close()

    if stats.get("queued", 0) < 1:
        print("\nWARN: expected queued >= 1 (worker may still be processing)")
    if stats.get("duplicates_blocked", 0) < 1:
        print("\nWARN: expected duplicates_blocked >= 1 for second comment")

    print("\nDone. Open http://127.0.0.1:8765/docs for interactive testing.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    raise SystemExit(main())
