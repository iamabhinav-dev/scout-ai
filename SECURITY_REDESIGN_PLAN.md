# Security Agent Redesign Plan

## Overview

Split passive security checks into **site-wide** (run once on root URL) and
**page-specific** (run per page using already-fetched HTML). Replace the per-page
Security score column in the audit table with a dedicated Security section that
shows findings grouped by scope.

---

## Phase 1 — Backend: Split the Scanner

**File: `backend/tools/security_scanner.py`**

Add two focused functions alongside the existing `scan_url_passive`:

### 1a. `scan_site_wide(url: str) → Dict`
One HTTP fetch. Runs checks whose results are **identical across all pages**:
- `_check_security_headers` (CSP, HSTS, X-Frame-Options, XCTO, Referrer-Policy, Permissions-Policy)
- `_check_cookie_security` (Secure, HttpOnly, SameSite on Set-Cookie headers)
- HTTP-vs-HTTPS protocol check (first part of `_check_transport_and_dom`)
- Server version / X-Powered-By disclosure

Returns `{ url, findings, headers, final_url, status_code }`.

### 1b. `scan_page_content(url: str, final_url: str, raw_html: str) → List[Dict]`
**No HTTP fetch** — accepts already-scraped HTML. Runs checks that **vary per page**:
- Mixed content asset references (`<script>`, `<img>`, `<iframe>`, `<link>` over HTTP)
- Login form without CSRF token (only on pages with password fields)
- Sensitive internal paths linked (`/.env`, `/admin`, `/.git`, etc.)
- Error / stack trace signature in page body
- Secret keyword patterns in page source (`api_key`, `authorization: bearer`, etc.)

Returns a `List[Dict]` of findings (same shape as existing findings).

**File: `backend/agents/security_agent.py`**

### 1c. `run_site_wide_security_audit(root_url: str) → Dict`
Calls `scan_site_wide(root_url)`, computes `overall_score` and `counts`.
Returns `{ overall_score, counts, findings, mode: "passive/site-wide" }`.

### 1d. `run_page_content_security_check(url, final_url, raw_html) → Dict`
Calls `scan_page_content(...)`, returns `{ findings }` (no aggregate score — these are
per-page additions rolled into the overall site score later).

Existing `run_security_audit` is kept unchanged for the single-page `/audit` endpoint.

---

## Phase 2 — Backend: Update `main.py`

### 2a. Separate LangGraph for site audits

Create a second compiled graph **`scout_graph_no_security`** that has the same
fan-out/fan-in structure but **excludes the `security_auditor` node**. This avoids
one redundant HTTP fetch per crawled page.

```
scrape → [ui_auditor, ux_auditor, compliance_auditor, seo_auditor] → merge → END
```

Add a helper `_run_graph_site(url: str) → dict` that uses this graph and also
returns `page_context` (the raw scrape result including `dom` / `raw_html`) so the
caller can run content-only security checks without a second fetch.

Keep `scout_graph` (with security_auditor) for the single-page `/audit` endpoint.

### 2b. Site-wide security run once in `/audit/site`

At the start of `_stream()`, immediately after `create_security_session`, run:

```python
site_wide_report = await asyncio.to_thread(
    run_site_wide_security_audit, root_url
)
```

`root_url` is derived from the first URL in `req.urls` (or `req.session_id`'s origin).

Persist site-wide findings to `security_findings` tagged with `scope="site_wide"`.
Store `site_wide_report` in a closure variable accessible to `_audit_one`.

### 2c. Per-page content security in `_audit_one`

After `_run_graph_site(url)` returns, extract `page_context` and call:

```python
page_sec_findings = await asyncio.to_thread(
    run_page_content_security_check,
    url,
    page_context.get("final_url", url),
    page_context.get("dom", ""),
)
```

Persist only non-empty `page_sec_findings` to `security_findings` tagged with
`scope="page_content"` and the specific `url`.

Include `page_security_findings` in the `page_audit_complete` SSE event — only when
the list is non-empty (saves bandwidth on clean pages).

### 2d. `site_audit_complete` event additions

Include in the final SSE event:

```json
{
  "type": "site_audit_complete",
  "security_session_id": "...",
  "security_overall_score": 72,
  "security_counts": { "critical": 0, "high": 3, "medium": 4, "low": 2 },
  "security_site_wide_findings": [ ...findings... ]
}
```

This gives the frontend everything it needs without an extra API call.

### 2e. `GET /crawl/{session_id}/audit` enrichment

When reloading a past audit, fetch security findings with the `scope` column so the
response can split `site_wide_findings` vs `page_content_findings` per URL.

### 2f. Database: add `scope` column

Add `scope TEXT NOT NULL DEFAULT 'site_wide'` to `security_findings` table.

Migration SQL (to run in Supabase):

```sql
ALTER TABLE security_findings
  ADD COLUMN IF NOT EXISTS scope TEXT NOT NULL DEFAULT 'site_wide';
```

---

## Phase 3 — Frontend: Per-page Table Changes

**File: `frontend/components/nonprimitive/SiteAuditResults.tsx`**

### 3a. Remove Security score column

Remove the `<th>Security</th>` header and its corresponding `<td>` score cell from
every row. The table returns to 5 score columns: UI, UX, SEO, Risk + Status.

### 3b. Add page-issues badge

In the Page cell (path column), render a compact badge when a page has
page-specific security findings:

```tsx
{pageSecIssueCount > 0 && (
  <span className="ml-2 rounded bg-amber-500/20 px-1.5 py-0.5 text-[10px] font-semibold text-amber-300">
    {pageSecIssueCount} sec issue{pageSecIssueCount > 1 ? "s" : ""}
  </span>
)}
```

`pageSecIssueCount` is derived from `page.pageSecurityFindings?.length ?? 0`.

### 3c. Update `PageAuditResult` type in `useSiteAuditStream.ts`

```ts
// Remove:
securityReport: Record<string, any> | null;

// Add:
pageSecurityFindings: Array<Record<string, any>> | null;  // page-content findings only
```

Populate `pageSecurityFindings` from `ev.page_security_findings` in the
`page_audit_complete` handler (may be absent / empty array for clean pages).

---

## Phase 4 — Frontend: Dedicated Security Section

### 4a. Update `useSiteAuditStream.ts`

Add to the hook's return value:

```ts
siteSecurityReport: {
  overall_score: number;
  counts: { critical: number; high: number; medium: number; low: number };
  site_wide_findings: Array<Record<string, any>>;
} | null;
```

Populate from the `site_audit_complete` SSE event fields added in Phase 2d.

### 4b. Refactor `SecurityAuditResults.tsx`

Update `Props`:

```ts
interface Props {
  siteReport: { overall_score, counts, site_wide_findings } | null;
  pageAudits: Map<string, PageAuditResult>;   // to pull per-page findings
  auditStatus: AuditStatus;
}
```

Layout (top to bottom):

1. **Score + counts bar** — existing 6-box grid (Score / Critical / High / Medium / Low / Total)
2. **Site-wide findings table** — findings from `site_wide_findings`, Page column shows
   "Site-wide" label (not a URL) with a globe icon
3. **Page-specific findings table** — flatten `pageSecurityFindings` from all
   `pageAudits` entries, Page column shows truncated path with link; show only when
   at least one page has findings; show "No page-specific issues" otherwise

Remove the dependency on `useSecurityAudit` hook entirely — all data comes through
`useSiteAuditStream`.

### 4c. Update `CrawlerDashboard.tsx`

Import and wire `SecurityAuditResults`:

```tsx
import SecurityAuditResults from "@/components/nonprimitive/SecurityAuditResults";

// In useSiteAuditStream destructure:
const { ..., siteSecurityReport } = useSiteAuditStream(...);

// Below <SiteAuditResults>:
{auditEnabled && (
  <SecurityAuditResults
    siteReport={siteSecurityReport}
    pageAudits={pageAudits}
    auditStatus={auditStatus}
  />
)}
```

The section appears below the per-page table and auto-scrolls into view when the
audit completes (reuse existing `auditSectionRef` scroll logic or add a second ref).

---

## Summary of File Changes

| File | Change |
|---|---|
| `backend/tools/security_scanner.py` | Add `scan_site_wide`, `scan_page_content` |
| `backend/agents/security_agent.py` | Add `run_site_wide_security_audit`, `run_page_content_security_check` |
| `backend/main.py` | New `scout_graph_no_security`, `_run_graph_site`, site-wide run-once, per-page content check, updated SSE events |
| `frontend/hooks/useSiteAuditStream.ts` | Replace `securityReport` with `pageSecurityFindings`; add `siteSecurityReport` |
| `frontend/components/nonprimitive/SiteAuditResults.tsx` | Remove Security column; add per-page issues badge |
| `frontend/components/nonprimitive/SecurityAuditResults.tsx` | New props; split site-wide vs page-specific tables |
| `frontend/components/nonprimitive/CrawlerDashboard.tsx` | Import and render `SecurityAuditResults` |
| Supabase (manual) | `ALTER TABLE security_findings ADD COLUMN scope TEXT` |

---

## Implementation Order

1. Phase 1 (scanner split) — pure additions, no regressions
2. Phase 2a–2c (main.py graph + per-page check) — backend logic
3. Phase 2d–2e (SSE events + DB reload enrichment) — backend wire-up
4. Run Supabase migration (Phase 2f)
5. Phase 3 (table cleanup) — frontend
6. Phase 4 (security section) — frontend
