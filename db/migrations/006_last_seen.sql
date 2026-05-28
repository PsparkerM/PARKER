-- Migration 006: Add last_seen column to users
-- Run once in Supabase Dashboard → SQL Editor

ALTER TABLE users ADD COLUMN IF NOT EXISTS last_seen timestamptz;

CREATE INDEX IF NOT EXISTS idx_users_last_seen ON users (last_seen DESC NULLS LAST);
