#!/usr/bin/env python3
"""Compare local /stats with Pseudogram simulate truth. Requires env vars below."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import httpx

BASE = os.environ.get("PSEUDOGRAM_BASE_URL", "https://pseudogram-api.onrender.com").rstrip("/")
API_KEY = os.environ.get("PSEUDOGRAM_API_KEY", "")
APP_URL = os.environ.get("APP_URL", "").rstrip("/")


def headers() -> dict[str, str]:
    return {"X-API-Key": API_KEY, "Content-Type": "application/json"}


def start_simulate(count: int, duration: int) -> str:
    response = httpx.post(
        f"{BASE}/v1/simulate/start",
        headers=headers(),
        json={"webhook_url": f"{APP_URL}/webhook", "count": count, "duration_seconds": duration},
        timeout=30.0,
    )
    response.raise_for_status()
    run_id = response.json()["run_id"]
    print(f"simulate run_id={run_id}")
    return run_id


def fetch_truth(run_id: str) -> dict:
    response = httpx.get(f"{BASE}/v1/simulate/{run_id}/truth", headers=headers(), timeout=30.0)
    response.raise_for_status()
    return response.json()


def fetch_stats() -> dict:
    response = httpx.get(f"{APP_URL}/stats", timeout=10.0)
    response.raise_for_status()
    return response.json()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=500)
    parser.add_argument("--duration", type=int, default=10)
    parser.add_argument("--wait", type=int, default=120, help="Seconds to wait before comparing stats")
    args = parser.parse_args()

    if not API_KEY or not APP_URL:
        print("Set PSEUDOGRAM_API_KEY and APP_URL env vars", file=sys.stderr)
        return 1

    run_id = start_simulate(args.count, args.duration)
    print(f"Waiting {args.wait}s for worker + reconciler to drain...")
    time.sleep(args.wait)

    stats = fetch_stats()
    truth = fetch_truth(run_id)
    print("\nYour /stats:")
    print(json.dumps(stats, indent=2))
    print("\nPseudogram truth (excerpt):")
    for key in ("expected_sent", "expected_failed", "expected_queued", "expected_duplicates_blocked", "sent", "failed", "queued", "duplicates_blocked"):
        if key in truth:
            print(f"  {key}: {truth[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
