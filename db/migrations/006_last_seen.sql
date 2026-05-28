-- ============================================================
-- Migration 006: last_seen column for user activity tracking
--
-- Tracks the last time a user opened the bot (/start).
-- Run ONCE in Supabase Dashboard → SQL Editor
-- ============================================================

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS last_seen timestamptz;

-- Index for sorting by recent activity
CREATE INDEX IF NOT EXISTS idx_users_last_seen ON users (last_seen DESC NULLS LAST);
