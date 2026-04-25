-- Add multi-time support for meal reminders
-- Run once in Supabase SQL Editor

ALTER TABLE reminders ADD COLUMN IF NOT EXISTS times  jsonb;
ALTER TABLE reminders ADD COLUMN IF NOT EXISTS labels jsonb;
