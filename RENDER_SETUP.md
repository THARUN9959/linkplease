# Deploy to Render — THARUN9959

Target repo: **https://github.com/THARUN9959/linkplease**

## Part A — Push to GitHub (one time)

1. Open https://github.com/new
2. Repository name: `linkplease`
3. Visibility: **Public**
4. Do **not** add README, .gitignore, or license (we already have them)
5. Click **Create repository**

In PowerShell from this folder:

```powershell
git remote add origin https://github.com/THARUN9959/linkplease.git
git branch -M main
git push -u origin main
```

Sign in as **THARUN9959** when Git prompts you.

---

## Part B — Deploy on Render (Blueprint)

1. Sign up / log in at https://dashboard.render.com
2. Connect your **GitHub** account and authorize **THARUN9959**
3. Click **New +** → **Blueprint**
4. Connect repository **THARUN9959/linkplease**
5. Render reads `render.yaml` and creates:
   - Web service `linkplease`
   - Postgres database `linkplease-db`
6. When prompted for env vars, set:
   - **`PSEUDOGRAM_API_KEY`** = your real key from `python scripts/setup_pseudogram.py --skip-apply --email YOUR_EMAIL`
7. Click **Apply** / **Deploy**

Wait until status is **Live**. Your URL will look like:

`https://linkplease-xxxx.onrender.com`

---

## Part C — Post-deploy checks

```powershell
# Health
curl https://YOUR-APP.onrender.com/health

# Create rule (required before grading)
curl -X POST https://YOUR-APP.onrender.com/rules `
  -H "Content-Type: application/json" `
  -d "{\"keyword\":\"PRICE\",\"dm_message\":\"Here is the price list\"}"

# Stats
curl https://YOUR-APP.onrender.com/stats
```

Simulate against production:

```powershell
$env:PSEUDOGRAM_API_KEY="your-key"
$env:APP_URL="https://YOUR-APP.onrender.com"
python scripts/compare_truth.py --wait 180
```

---

## Part D — Submit

```json
POST https://pseudogram-api.onrender.com/v1/submit

{
  "email": "YOUR_APPLY_EMAIL",
  "github_repo": "https://github.com/THARUN9959/linkplease",
  "working_url": "https://YOUR-APP.onrender.com",
  "loom_url": "https://loom.com/share/...",
  "parts_completed": "A+B+C",
  "start_date": "2026-08-16"
}
```

---

## Troubleshooting

| Issue | Fix |
|---|---|
| Build fails on `alembic` | Check Render logs; `DATABASE_URL` must come from linked Postgres |
| Webhooks 401 | Set real `PSEUDOGRAM_API_KEY` on Render and redeploy |
| Service sleeps (free tier) | Upgrade to paid or use a cron ping before deadline |
| `git push` rejected | Create empty `linkplease` repo on GitHub first |

Keep the Render URL live for **7 days after 17 Aug 2026**.
