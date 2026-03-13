# RecallAlert — Automated Pipeline Setup Guide
## From 1,035 recalls → 50,000+ recalls, updated daily. Zero cost.

---

## What this does

NHTSA publishes their complete recall database as a flat file that updates daily.
This pipeline downloads it automatically, parses all 50,000+ records, and stores
them in your Supabase database. Your site then queries Supabase directly.

**Result:** Every vehicle recall in the NHTSA database, 2010–present, updated daily.

---

## Step 1 — Run the Supabase SQL setup (once, ~2 minutes)

1. Go to https://supabase.com/dashboard → your project → **SQL Editor**
2. Paste the contents of `supabase_setup.sql`
3. Click **Run**
4. You should see: `Setup complete! Tables created.`

---

## Step 2 — Create a GitHub repository (once, ~3 minutes)

1. Go to https://github.com/new
2. Name it `recallalert-pipeline`
3. Set it to **Public** (free Actions minutes)
4. Don't initialize with README (you'll push your own files)

---

## Step 3 — Add Supabase secrets to GitHub (once, ~2 minutes)

In your new GitHub repo:
1. Go to **Settings → Secrets and variables → Actions → New repository secret**

Add these two secrets:

| Secret name | Value |
|---|---|
| `SUPABASE_URL` | `https://eyprbgcvfsmlarxljszx.supabase.co` |
| `SUPABASE_SERVICE_KEY` | *(your service_role key from Supabase → Settings → API)* |

> ⚠️ Use the **service_role** key (not the anon key) — the pipeline needs write access.
> The service_role key stays in GitHub Secrets and is never exposed to the browser.

---

## Step 4 — Push the pipeline files (once, ~2 minutes)

```bash
cd recallalert-pipeline
git init
git remote add origin https://github.com/YOUR_USERNAME/recallalert-pipeline.git
git add .
git commit -m "Initial pipeline setup"
git push -u origin main
```

GitHub Actions will automatically detect the workflow file and schedule it.

---

## Step 5 — Run the first sync manually (once, ~5 minutes)

1. In your GitHub repo, go to **Actions → Sync NHTSA Recall Data**
2. Click **Run workflow → Run workflow**
3. Watch the logs — you'll see it download ~20MB and upsert ~50,000 rows
4. When complete, go to Supabase → Table Editor → `vehicle_recalls` to confirm data

---

## Step 6 — Swap the vehicle query in index.html (once, ~1 minute)

Once the pipeline has populated Supabase, swap the vehicle fetch function:

1. Open `index.html`
2. Find the `async function fetchVehicles()` block
3. Replace it with the contents of `supabase_query.js`
4. Redeploy to Netlify

Your site now serves from Supabase — 50,000+ recalls, instant search, no API limits.

---

## Ongoing: fully automatic

After setup, the pipeline runs **every day at 2:00 AM UTC** with no action needed.
NHTSA updates their flat file daily, so your data is always current.

You can monitor runs at: `https://github.com/YOUR_USERNAME/recallalert-pipeline/actions`

---

## Data coverage after pipeline is live

| Source | Records | Update frequency |
|---|---|---|
| NHTSA flat file (vehicle_recalls) | ~50,000+ | Daily (auto) |
| FDA openFDA (food/drug/device) | ~80,000+ | Real-time API |
| USDA FSIS (meat/poultry) | ~5,000+ | Real-time API |
| CPSC (products) | ~10,000+ | Real-time API |

---

## Cost breakdown

| Service | Cost |
|---|---|
| GitHub Actions (public repo) | Free |
| Supabase free tier (500MB DB) | Free |
| Netlify hosting | Free |
| Domain (recallalert.com) | ~$12/year |
| **Total** | **~$12/year** |

The NHTSA data fits well within Supabase's free tier:
- ~50,000 rows × ~800 bytes avg = ~40MB (well under 500MB limit)
- Supabase free tier: unlimited API requests, 5GB bandwidth/month

---

## Troubleshooting

**Pipeline fails with download error:**
NHTSA occasionally takes their flat file down for maintenance. The next day's run
will succeed automatically. Check https://static.nhtsa.gov/odi/ffdd/rcl/ for status.

**"read-only mode" in Supabase:**
You've hit the 500MB free tier limit. Unlikely with this data size, but if it happens:
either upgrade to Pro ($25/month) or reduce stored fields to shrink row size.

**Search not working after Supabase swap:**
Supabase's `ilike` search is case-insensitive. If you need full-text search,
use the `fts` column with Supabase's `websearch_to_tsquery` function.
