#!/usr/bin/env python3
"""Apply for Pseudogram access and fetch API key into .env."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import httpx

BASE = "https://pseudogram-api.onrender.com"
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def load_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def save_api_key(path: Path, api_key: str) -> None:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if re.search(r"^PSEUDOGRAM_API_KEY=.*$", text, flags=re.MULTILINE):
        text = re.sub(r"^PSEUDOGRAM_API_KEY=.*$", f"PSEUDOGRAM_API_KEY={api_key}", text, flags=re.MULTILINE)
    else:
        text = (text.rstrip() + f"\nPSEUDOGRAM_API_KEY={api_key}\n").lstrip()
    path.write_text(text, encoding="utf-8")


def apply(client: httpx.Client, payload: dict) -> None:
    response = client.post(f"{BASE}/v1/apply", json=payload)
    print("apply:", response.status_code, response.text)
    response.raise_for_status()


def keygen(client: httpx.Client, email: str) -> str:
    response = client.post(f"{BASE}/v1/keygen", json={"email": email})
    print("keygen:", response.status_code, response.text)
    response.raise_for_status()
    body = response.json()
    return body["api_key"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Register with Pseudogram and save API key to .env")
    parser.add_argument("--name", default=os.environ.get("PSEUDOGRAM_NAME"))
    parser.add_argument("--email", default=os.environ.get("PSEUDOGRAM_EMAIL"))
    parser.add_argument("--phone", default=os.environ.get("PSEUDOGRAM_PHONE"))
    parser.add_argument("--whatsapp", default=os.environ.get("PSEUDOGRAM_WHATSAPP"))
    parser.add_argument("--linkedin-url", default=os.environ.get("PSEUDOGRAM_LINKEDIN_URL"))
    parser.add_argument("--skip-apply", action="store_true", help="Only run keygen (already applied)")
    args = parser.parse_args()

    env = load_dotenv(ENV_PATH)
    name = args.name or env.get("PSEUDOGRAM_NAME")
    email = args.email or env.get("PSEUDOGRAM_EMAIL")
    phone = args.phone or env.get("PSEUDOGRAM_PHONE")
    whatsapp = args.whatsapp or env.get("PSEUDOGRAM_WHATSAPP") or phone
    linkedin = args.linkedin_url or env.get("PSEUDOGRAM_LINKEDIN_URL")

    if not email:
        print("Missing email. Pass --email or set PSEUDOGRAM_EMAIL in .env", file=sys.stderr)
        return 1

    with httpx.Client(timeout=30.0) as client:
        if not args.skip_apply:
            missing = [k for k, v in {"name": name, "phone": phone, "linkedin_url": linkedin}.items() if not v]
            if missing:
                print(f"Missing apply fields: {', '.join(missing)}", file=sys.stderr)
                print("Fill .env from .env.example or pass CLI flags.", file=sys.stderr)
                return 1
            apply(
                client,
                {
                    "name": name,
                    "email": email,
                    "phone": phone,
                    "whatsapp": whatsapp,
                    "linkedin_url": linkedin,
                },
            )

        api_key = keygen(client, email)
        save_api_key(ENV_PATH, api_key)
        print(f"\nSaved PSEUDOGRAM_API_KEY to {ENV_PATH}")
        print("Restart uvicorn so the server picks up the new key.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
