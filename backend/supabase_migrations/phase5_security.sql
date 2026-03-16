-- =============================================================================
-- Scout.ai — Phase 5 Security Agent (V1 passive)
-- Safe to run multiple times (idempotent where possible)
-- =============================================================================

CREATE TABLE IF NOT EXISTS security_sessions (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    crawl_session_id UUID        NOT NULL REFERENCES crawl_sessions(id) ON DELETE CASCADE,
    user_id          UUID        REFERENCES profiles(id) ON DELETE SET NULL,
    mode             TEXT        NOT NULL DEFAULT 'passive',
    status           TEXT        NOT NULL DEFAULT 'running',
    overall_score    FLOAT,
    scanned_pages    INTEGER     NOT NULL DEFAULT 0,
    critical_count   INTEGER     NOT NULL DEFAULT 0,
    high_count       INTEGER     NOT NULL DEFAULT 0,
    medium_count     INTEGER     NOT NULL DEFAULT 0,
    low_count        INTEGER     NOT NULL DEFAULT 0,
    started_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at     TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS security_findings (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    security_session_id UUID        NOT NULL REFERENCES security_sessions(id) ON DELETE CASCADE,
    page_id             UUID        REFERENCES crawled_pages(id) ON DELETE SET NULL,
    url                 TEXT        NOT NULL,
    category            TEXT        NOT NULL,
    title               TEXT        NOT NULL,
    description         TEXT        NOT NULL,
    severity            TEXT        NOT NULL,
    confidence          TEXT        NOT NULL,
    recommendation      TEXT        NOT NULL,
    evidence_json       JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_security_sessions_crawl_session_id
    ON security_sessions(crawl_session_id);

CREATE INDEX IF NOT EXISTS idx_security_sessions_user_id
    ON security_sessions(user_id);

CREATE INDEX IF NOT EXISTS idx_security_findings_security_session_id
    ON security_findings(security_session_id);

CREATE INDEX IF NOT EXISTS idx_security_findings_page_id
    ON security_findings(page_id);

CREATE INDEX IF NOT EXISTS idx_security_findings_severity
    ON security_findings(severity);

ALTER TABLE security_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE security_findings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "users own their security sessions" ON security_sessions;
CREATE POLICY "users own their security sessions"
    ON security_sessions
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

DROP POLICY IF EXISTS "users own their security findings" ON security_findings;
CREATE POLICY "users own their security findings"
    ON security_findings
    USING (
        security_session_id IN (
            SELECT id FROM security_sessions WHERE user_id = auth.uid()
        )
    );
