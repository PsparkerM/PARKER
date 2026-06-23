-- Migration 009: renewal reminder flag
-- Помечает момент, когда пользователю уже отправили напоминание о скором
-- окончании подписки, чтобы планировщик не слал его повторно каждый день.
-- Сбрасывается в NULL при продлении (upsert_subscription), чтобы в следующем
-- периоде напоминание ушло снова.

ALTER TABLE subscriptions
    ADD COLUMN IF NOT EXISTS renewal_notified_at timestamptz;
