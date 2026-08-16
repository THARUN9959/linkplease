#!/usr/bin/env python3
"""Send a signed webhook to the local (or deployed) LinkPlease server."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def load_api_key() -> str:
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("PSEUDOGRAM_API_KEY="):
                return line.split("=", 1)[1].strip()
    return os.environ.get("PSEUDOGRAM_API_KEY", "replace-me")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.environ.get("APP_URL", "http://127.0.0.1:8765"))
    parser.add_argument("--keyword-text", default="PRICE please")
    parser.add_argument("--wait", type=int, default=5)
    args = parser.parse_args()

    from app.services.signature import compute_signature

    api_key = load_api_key()
    if api_key in ("", "replace-me"):
        print("WARN: using placeholder API key. Run scripts/setup_pseudogram.py first.")

    base = args.base_url.rstrip("/")
    client = httpx.Client(base_url=base, timeout=15.0)

    print("Creating rule...")
    rule = client.post("/rules", json={"keyword": "PRICE", "dm_message": "Here is the price list"}).json()
    print(" rule:", rule)

    payload = {
        "event_id": f"evt_local_{int(time.time())}",
        "event_type": "comment.created",
        "sent_at": "2026-08-10T09:14:22.481Z",
        "data": {
            "comment_id": f"cmt_local_{int(time.time())}",
            "post_id": "post_local",
            "text": args.keyword_text,
            "created_at": "2026-08-10T09:14:21.900Z",
            "from": {"user_id": "usr_local_test", "username": "local.tester"},
        },
    }
    body = json.dumps(payload).encode()
    headers = {
        "Content-Type": "application/json",
        "X-PseudoGram-Signature": compute_signature(body, api_key),
    }

    print("Posting webhook...")
    response = client.post("/webhook", content=body, headers=headers)
    print(" webhook:", response.status_code, response.text)

    print(f"Waiting {args.wait}s for worker...")
    time.sleep(args.wait)
    stats = client.get("/stats").json()
    print("stats:", json.dumps(stats, indent=2))
    client.close()
    return 0 if response.status_code == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
