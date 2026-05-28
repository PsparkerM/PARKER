-- Migration 007: subscriptions table
-- Tracks Telegram Stars payments and Pro subscription periods.
-- On payment: upsert here + set users.status = 'pro'
-- On expiry:  set status = 'expired' here + set users.status = 'free'

CREATE TABLE IF NOT EXISTS subscriptions (
    id                  uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id             uuid        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan                text        NOT NULL CHECK (plan IN ('monthly', 'annual')),
    status              text        NOT NULL DEFAULT 'active'
                                    CHECK (status IN ('active', 'expired', 'cancelled')),
    telegram_charge_id  text,
    starts_at           timestamptz NOT NULL DEFAULT now(),
    expires_at          timestamptz NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id)
);

ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all" ON subscriptions
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);
