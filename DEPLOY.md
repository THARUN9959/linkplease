# Deploy checklist (Render)

## 1. Pseudogram API key

Edit `.env` with your details (copy from `.env.example`), then:

```bash
python scripts/setup_pseudogram.py
# already applied? use:
python scripts/setup_pseudogram.py --skip-apply --email you@example.com
```

Restart uvicorn after the key is saved.

## 2. Local webhook test

```bash
python scripts/local_webhook_test.py --base-url http://127.0.0.1:8765 --wait 8
python scripts/local_smoke.py
```

With a real API key, `queued` should stay at 1 and the worker will call Pseudogram (may eventually show `sent` or `failed`).

## 3. Push to GitHub

```bash
git init
git add .
git commit -m "LinkPlease assignment: FastAPI A+B+C implementation"
git branch -M main
git remote add origin https://github.com/YOUR_USER/linkplease.git
git push -u origin main
```

Repo must be **public** and include `FAILURES.md` at the root.

## 4. Deploy on Render

1. Go to [render.com](https://render.com) → **New** → **Blueprint** → connect GitHub repo.
2. Render reads `render.yaml` (Web Service + Postgres).
3. Set `PSEUDOGRAM_API_KEY` in the dashboard (sync: false in blueprint).
4. Wait for deploy; note URL like `https://linkplease-xxxx.onrender.com`.

Or manually: Python web service, build `pip install -r requirements.txt`, start `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`, attach Postgres, set env vars.

## 5. Seed rule on production

```bash
curl -X POST https://YOUR-APP.onrender.com/rules \
  -H "Content-Type: application/json" \
  -d "{\"keyword\":\"PRICE\",\"dm_message\":\"Here is the price list\"}"
```

## 6. Simulate + compare truth

```bash
set PSEUDOGRAM_API_KEY=your-key
set APP_URL=https://YOUR-APP.onrender.com
python scripts/compare_truth.py --wait 180
```

## 7. Submit

```bash
curl -X POST https://pseudogram-api.onrender.com/v1/submit \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"you@example.com\",\"github_repo\":\"https://github.com/you/linkplease\",\"working_url\":\"https://YOUR-APP.onrender.com\",\"loom_url\":\"https://loom.com/share/...\",\"parts_completed\":\"A+B+C\",\"start_date\":\"2026-08-16\"}"
```

Keep the URL live for **7 days** after the deadline (17 Aug 2026, 11:59 PM IST).
