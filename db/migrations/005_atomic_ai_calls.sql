-- ============================================================
-- Migration 005: Atomic AI call counter via PostgreSQL function
--
-- Replaces the non-atomic Python read→check→write pattern that
-- allowed concurrent requests to bypass the daily AI quota.
--
-- Run ONCE in Supabase Dashboard → SQL Editor
-- ============================================================

CREATE OR REPLACE FUNCTION increment_ai_calls(p_user_id uuid, p_date date)
RETURNS int
LANGUAGE sql
SECURITY DEFINER
AS $$
  INSERT INTO ai_usage (user_id, used_date, call_count)
  VALUES (p_user_id, p_date, 1)
  ON CONFLICT (user_id, used_date)
  DO UPDATE SET call_count = ai_usage.call_count + 1
  RETURNING call_count;
$$;

-- Allow service_role (the only role the server uses) to call it.
-- Anon / authenticated roles are blocked by RLS on ai_usage.
GRANT EXECUTE ON FUNCTION increment_ai_calls(uuid, date) TO service_role;

-- ── Verify ───────────────────────────────────────────────────
-- SELECT increment_ai_calls('<any-user-uuid>', CURRENT_DATE);
-- Run twice → should return 1 then 2.
