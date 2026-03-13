-- ============================================================
-- RecallAlert — Supabase Setup
-- Run this ONCE in your Supabase SQL Editor (one-time setup)
-- ============================================================

-- Vehicle recalls table (populated by GitHub Actions daily)
CREATE TABLE IF NOT EXISTS vehicle_recalls (
  id               BIGSERIAL PRIMARY KEY,
  campaign_number  TEXT NOT NULL,       -- e.g. "24V001000"
  make             TEXT,                -- e.g. "FORD"
  model            TEXT,                -- e.g. "F-150"
  model_year       TEXT,                -- e.g. "2022"
  manufacturer     TEXT,                -- e.g. "FORD MOTOR COMPANY"
  component        TEXT,                -- e.g. "AIR BAGS"
  defect_summary   TEXT,
  consequence      TEXT,
  remedy           TEXT,
  recall_date      DATE,                -- parsed from RCDATE
  potentially_affected INTEGER,
  recall_type      TEXT,                -- V=vehicle, T=tire, E=equipment, C=childseat
  updated_at       TIMESTAMPTZ DEFAULT NOW(),

  -- Unique constraint: one row per campaign+make+model+year
  UNIQUE (campaign_number, make, model, model_year)
);

-- Indexes for fast filtering and search
CREATE INDEX IF NOT EXISTS idx_vr_make       ON vehicle_recalls (make);
CREATE INDEX IF NOT EXISTS idx_vr_model      ON vehicle_recalls (model);
CREATE INDEX IF NOT EXISTS idx_vr_year       ON vehicle_recalls (model_year);
CREATE INDEX IF NOT EXISTS idx_vr_date       ON vehicle_recalls (recall_date DESC);
CREATE INDEX IF NOT EXISTS idx_vr_component  ON vehicle_recalls USING gin(to_tsvector('english', COALESCE(component,'')));
CREATE INDEX IF NOT EXISTS idx_vr_defect     ON vehicle_recalls USING gin(to_tsvector('english', COALESCE(defect_summary,'')));
CREATE INDEX IF NOT EXISTS idx_vr_campaign   ON vehicle_recalls (campaign_number);

-- Full-text search index (make + model + component + defect)
CREATE INDEX IF NOT EXISTS idx_vr_fts ON vehicle_recalls
  USING gin(to_tsvector('english',
    COALESCE(make,'') || ' ' ||
    COALESCE(model,'') || ' ' ||
    COALESCE(component,'') || ' ' ||
    COALESCE(defect_summary,'')
  ));

-- Enable public read access (no auth needed for the site)
ALTER TABLE vehicle_recalls ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read access"
  ON vehicle_recalls FOR SELECT
  TO anon
  USING (true);

-- ============================================================
-- Optional: pipeline_log table to track sync runs
-- ============================================================
CREATE TABLE IF NOT EXISTS pipeline_log (
  id           BIGSERIAL PRIMARY KEY,
  run_at       TIMESTAMPTZ DEFAULT NOW(),
  source       TEXT,          -- 'nhtsa_flat_file'
  rows_upserted INTEGER,
  duration_ms  INTEGER,
  status       TEXT,          -- 'success' | 'error'
  message      TEXT
);

-- Allow the pipeline (service role) to insert logs
ALTER TABLE pipeline_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role insert"
  ON pipeline_log FOR INSERT
  TO service_role
  USING (true);

-- Done! Now push the pipeline files to GitHub and add secrets.
SELECT 'Setup complete! Tables created.' AS status;
