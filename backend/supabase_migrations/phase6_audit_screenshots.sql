-- =============================================================================
-- Phase 6: Screenshot storage via Supabase Storage buckets
-- Safe to run multiple times (idempotent).
-- =============================================================================

-- Store the public URL of the screenshot uploaded to the "screenshots" bucket.
-- Replaces the old screenshot_b64 TEXT approach (base64 in DB was too large).

-- crawled_pages: screenshot taken during BFS crawl
ALTER TABLE crawled_pages
    ADD COLUMN IF NOT EXISTS screenshot_url TEXT;

-- page_audits: screenshot taken during vision_scraper audit
ALTER TABLE page_audits
    ADD COLUMN IF NOT EXISTS screenshot_url TEXT;

-- Migrate any existing base64 data is NOT handled here — new screenshots
-- will use storage URLs.  Old screenshot_b64 columns can be dropped later
-- once confirmed no longer needed.
