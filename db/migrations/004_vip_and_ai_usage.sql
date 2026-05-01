-- ============================================================
-- Migration 004: VIP statuses + AI usage tracking
--
-- Run this ONCE in Supabase Dashboard:
--   Project → SQL Editor → paste → Run
-- ============================================================


-- ── Part 1: Set VIP status for existing users ─────────────
-- Moves hardcoded VIP_USER_IDS from source code into the DB.
-- Run only once; repeated runs are safe (idempotent UPDATE).

UPDATE users
SET    status = 'vip'
WHERE  tg_id IN (
    6135518022,   -- Петр   (admin)
    1199979214,   -- Лера
    923353879,    -- Вика
    494349908,    -- Артём
    1635982841    -- Аник
)
AND (status IS NULL OR status != 'vip');


-- ── Part 2: AI usage tracking table ──────────────────────
-- Replaces the in-memory _AI_DAILY dict.
-- Persists across Railway deployments.

CREATE TABLE IF NOT EXISTS ai_usage (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    used_date  date NOT NULL DEFAULT CURRENT_DATE,
    call_count int  NOT NULL DEFAULT 0,
    UNIQUE (user_id, used_date)
);

-- Index for fast per-user daily lookup
CREATE INDEX IF NOT EXISTS idx_ai_usage_user_date
    ON ai_usage (user_id, used_date);

-- RLS: deny all direct access (server uses service_role, bypasses RLS)
ALTER TABLE ai_usage ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "deny_ai_usage_all" ON ai_usage;
CREATE POLICY "deny_ai_usage_all"
    ON ai_usage AS RESTRICTIVE FOR ALL
    USING (false) WITH CHECK (false);


-- ── Verify ───────────────────────────────────────────────
-- Check that VIP updates applied:
--   SELECT tg_id, status FROM users WHERE tg_id IN (6135518022, 1199979214, 923353879, 494349908, 1635982841);
--
-- Check ai_usage table exists:
--   SELECT * FROM ai_usage LIMIT 1;
