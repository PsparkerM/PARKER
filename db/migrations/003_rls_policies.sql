-- ============================================================
-- RLS (Row Level Security) — Defense-in-depth for P.A.R.K.E.R.
--
-- Context:
--   The server uses SUPABASE_SERVICE_KEY (service_role), which
--   bypasses RLS entirely — that is correct and intentional.
--   These policies protect against:
--     1. Direct DB access via anon/authenticated Supabase keys
--     2. Accidental use of anon key in future code
--     3. Supabase Dashboard users without service_role
--
-- How it works:
--   Enabling RLS with NO permissive policies = deny-all for
--   anon and authenticated roles. Service_role is unaffected.
-- ============================================================

-- ── Enable RLS on all tables ─────────────────────────────────

ALTER TABLE users      ENABLE ROW LEVEL SECURITY;
ALTER TABLE plans      ENABLE ROW LEVEL SECURITY;
ALTER TABLE reminders  ENABLE ROW LEVEL SECURITY;

-- ── Drop any existing loose policies ─────────────────────────

DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT policyname, tablename
        FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename IN ('users', 'plans', 'reminders')
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS %I ON %I', r.policyname, r.tablename);
    END LOOP;
END;
$$;

-- ── Explicit DENY-ALL for anon and authenticated roles ────────
-- (No permissive policies = deny by default. These are
--  documented as restrictive policies for clarity.)

-- users
CREATE POLICY "deny_anon_users_select"    ON users    AS RESTRICTIVE FOR SELECT USING (false);
CREATE POLICY "deny_anon_users_insert"    ON users    AS RESTRICTIVE FOR INSERT WITH CHECK (false);
CREATE POLICY "deny_anon_users_update"    ON users    AS RESTRICTIVE FOR UPDATE USING (false);
CREATE POLICY "deny_anon_users_delete"    ON users    AS RESTRICTIVE FOR DELETE USING (false);

-- plans
CREATE POLICY "deny_anon_plans_select"    ON plans    AS RESTRICTIVE FOR SELECT USING (false);
CREATE POLICY "deny_anon_plans_insert"    ON plans    AS RESTRICTIVE FOR INSERT WITH CHECK (false);
CREATE POLICY "deny_anon_plans_update"    ON plans    AS RESTRICTIVE FOR UPDATE USING (false);
CREATE POLICY "deny_anon_plans_delete"    ON plans    AS RESTRICTIVE FOR DELETE USING (false);

-- reminders
CREATE POLICY "deny_anon_reminders_select"  ON reminders  AS RESTRICTIVE FOR SELECT USING (false);
CREATE POLICY "deny_anon_reminders_insert"  ON reminders  AS RESTRICTIVE FOR INSERT WITH CHECK (false);
CREATE POLICY "deny_anon_reminders_update"  ON reminders  AS RESTRICTIVE FOR UPDATE USING (false);
CREATE POLICY "deny_anon_reminders_delete"  ON reminders  AS RESTRICTIVE FOR DELETE USING (false);

-- ── Verify ───────────────────────────────────────────────────
-- After running, verify in Supabase Dashboard:
--   Authentication → Policies → each table should show RLS ON
--   and the four RESTRICTIVE policies.
--
-- Service role (SUPABASE_SERVICE_KEY) is UNAFFECTED — server
-- continues to work exactly as before.
