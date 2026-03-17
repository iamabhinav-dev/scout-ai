-- =============================================================================
-- Phase 7: Remove FK constraints from crawl_sessions / audit_sessions → profiles
-- =============================================================================
-- The profiles FK caused silent insert failures when a user signed in but no
-- matching profiles row existed (e.g. trigger not applied to existing accounts).
-- user_id is kept as a plain UUID — we only need it for owner-scoping queries.

ALTER TABLE crawl_sessions  DROP CONSTRAINT IF EXISTS fk_crawl_sessions_user;
ALTER TABLE audit_sessions   DROP CONSTRAINT IF EXISTS fk_audit_sessions_user;

-- Also relax the RLS INSERT policy so the service key can always insert.
-- The USING (read) policy is retained so users only see their own rows.
DROP POLICY IF EXISTS "users own their crawl sessions" ON crawl_sessions;
CREATE POLICY "users own their crawl sessions"
    ON crawl_sessions
    USING (user_id = auth.uid());

DROP POLICY IF EXISTS "users own their audit sessions" ON audit_sessions;
CREATE POLICY "users own their audit sessions"
    ON audit_sessions
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());
