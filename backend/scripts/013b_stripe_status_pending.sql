-- =============================================================================
-- Patch: Allow 'pending' in stripe_status CHECK constraint
-- Safe to re-run. Needed because create_checkout_session writes
-- stripe_status='pending' before redirecting to Stripe.
-- =============================================================================

-- Drop old constraint and re-add with 'pending' included
DO $$
BEGIN
    -- Find and drop the existing check constraint on stripe_status
    IF EXISTS (
        SELECT 1 FROM information_schema.constraint_column_usage
        WHERE table_name = 'subscriptions' AND column_name = 'stripe_status'
    ) THEN
        EXECUTE (
            SELECT 'ALTER TABLE subscriptions DROP CONSTRAINT ' || constraint_name
            FROM information_schema.constraint_column_usage
            WHERE table_name = 'subscriptions' AND column_name = 'stripe_status'
            LIMIT 1
        );
    END IF;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'No existing stripe_status constraint to drop: %', SQLERRM;
END $$;

ALTER TABLE subscriptions
    ADD CONSTRAINT subscriptions_stripe_status_check
    CHECK (stripe_status IN ('active', 'trialing', 'past_due', 'canceled', 'unpaid', 'incomplete', 'pending'));
