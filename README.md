# RecallAlert — Automated Data Pipeline

Runs daily via GitHub Actions. Downloads NHTSA flat file, processes all recalls, upserts to Supabase. Zero cost.

## Setup (one-time, ~10 minutes)
1. Create GitHub repo (public = free Actions)
2. Add secrets: SUPABASE_URL, SUPABASE_SERVICE_KEY  
3. Run SQL setup script in Supabase SQL editor once
4. Push this folder — pipeline runs automatically every day at midnight UTC

## What it does
- Downloads NHTSA FLAT_RCL_POST_2010.zip (~20MB) — all vehicle recalls 2010–present
- Parses pipe-delimited flat file (~50,000 rows)
- Upserts to Supabase `vehicle_recalls` table
- RecallAlert site queries Supabase directly — no backend needed
