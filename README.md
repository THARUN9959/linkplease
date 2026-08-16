# LinkPlease — comment-to-DM automation

FastAPI service for the LinkPlease intern assignment (Parts A+B+C). Incoming Instagram-style comment webhooks are matched against keyword rules and the commenter is DMed through the hostile Pseudogram mock API.

The assignment spec lives in [ASSIGNMENT.md](ASSIGNMENT.md). Honest leftover failure modes are in [FAILURES.md](FAILURES.md).

## API contract

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/webhook` | Comment events. Returns `200` immediately; work continues in the background. |
| `POST` | `/rules` | Create `{ keyword, dm_message }` → `201 { rule_id, keyword, dm_message }` |
| `GET` | `/stats` | `{ sent, failed, queued, duplicates_blocked }` from Postgres, not memory |
| `GET` | `/health` | Liveness for Render |

Keyword matching is case-insensitive and substring-based. Identity is `user_id`, not username. Duplicate `event_id`s are ignored. The same user is DMed at most once per rule.

## How it handles a hostile API

- Webhook HMAC-SHA256 verification (`X-PseudoGram-Signature`) using the API key as the secret.
- Durable event + outbound-DM rows in Postgres (unique constraints, not in-memory sets).
- Background send worker: rolling window of **9** `POST /v1/dm/send` calls per 60s (limit is 10).
- Retries on `429` (`Retry-After`) and `500` with exponential backoff. `400` is terminal.
- `Idempotency-Key` of `{rule_id}:{user_id}:{attempt}` so a crash after accept does not double-send.
- Reconciler polls `GET /v1/dm/{dm_id}` (not rate-limited). `delivered` increments `sent`. Late `failed` is retried with a new idempotency key until `MAX_SEND_ATTEMPTS`.
- `comment.deleted`: if the DM has not been accepted yet, the pending row is dropped. If the delete arrives first, the `comment_id` is recorded and a later `comment.created` is skipped.

## Local run

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # set PSEUDOGRAM_API_KEY after keygen
uvicorn app.main:app --reload --port 8000
```

Create a rule before simulating traffic:

```bash
curl -X POST http://127.0.0.1:8000/rules -H "Content-Type: application/json" -d "{\"keyword\":\"PRICE\",\"dm_message\":\"Here's the price list\"}"
```

Tests:

```bash
pytest -q
```

## Deploy on Render

1. Apply + keygen at `https://pseudogram-api.onrender.com`.
2. Push this repo to GitHub (public).
3. Create a Render Blueprint from `render.yaml`, or a Python web service + Postgres.
4. Set `PSEUDOGRAM_API_KEY`. `DATABASE_URL` comes from the Render Postgres instance (`postgres://` is rewritten to `postgresql+asyncpg://` on boot).
5. Tables are created on startup via SQLAlchemy `create_all` (Alembic is also available: `alembic upgrade head`).
6. Hit `POST /rules` on the public URL so the grader's comments have something to match.
7. Keep the service awake for 7 days after the deadline (Render free tier sleeps; a paid instance or an external ping is safer).

Seed a PRICE rule against the deployed host, then:

```bash
curl -X POST https://pseudogram-api.onrender.com/v1/simulate/start \
  -H "X-API-Key: $PSEUDOGRAM_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"webhook_url\":\"https://YOUR-APP.onrender.com/webhook\",\"count\":500,\"duration_seconds\":10}"
```

Compare `GET https://YOUR-APP.onrender.com/stats` with `GET /v1/simulate/{run_id}/truth`.
