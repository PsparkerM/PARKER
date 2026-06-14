-- Migration 008: normalized daily_logs table
-- One row per (user, day) for weight / sleep / water / steps / body measurements.
-- Replaces the per-day fields previously buried in the plans.content JSON blob,
-- enabling DB-side queries and analytics. Populated via best-effort dual-write
-- from /api/logs (blob remains the source of truth for reads until verified).
--
-- Food entries are intentionally NOT normalized here (multiple per day, already
-- handled well by the union-merge blob). This table is daily aggregates only.

CREATE TABLE IF NOT EXISTS daily_logs (
    id           uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id      uuid        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    log_date     date        NOT NULL,
    weight_kg    numeric,
    sleep_hours  numeric,
    water_ml     integer,
    steps        integer,
    waist_cm     numeric,
    hips_cm      numeric,
    chest_cm     numeric,
    thigh_cm     numeric,
    arm_cm       numeric,
    updated_at   timestamptz NOT NULL DEFAULT now(),
    created_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, log_date)
);

CREATE INDEX IF NOT EXISTS idx_daily_logs_user_date ON daily_logs (user_id, log_date DESC);

ALTER TABLE daily_logs ENABLE ROW LEVEL SECURITY;

-- service_role (server) bypasses RLS; deny-all for anon/authenticated is the
-- implicit default once RLS is enabled with no permissive policy for them.
CREATE POLICY "service_role_all" ON daily_logs
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);
