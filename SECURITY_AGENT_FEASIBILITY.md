# Security Agent Feasibility, Scope, and Solution Blueprint

## Executive Summary
Building a Security Agent in Scout AI is highly feasible and a strong product extension.

- Feasibility: High for passive web security checks using your existing crawler outputs.
- Time-to-first-value: 1 to 2 weeks for a useful V1.
- Risk profile: Manageable if you enforce strict safe-scanning boundaries.
- Strategic value: High. Security findings are urgent, easy to prioritize, and increase product stickiness.

Your current platform already has key primitives needed for this:
- Crawl session and page-level data
- Link graph and templates
- Screenshots and evidence handling
- Multi-agent reporting pipeline
- Account-aware project model and dashboard

## Why It Fits Scout AI Well
You already collect data that can be reused for security insights without major crawler changes:

- HTTP response headers
- URL patterns and query params
- Form discovery (login, search, contact, payment)
- Link graph for attack-surface mapping
- Page snapshots for proof/evidence
- Repeatable audit sessions for trend tracking

This enables a security agent that is immediately useful, even before advanced penetration tests.

## Recommended Product Positioning
Position this as:

"Security posture and web vulnerability signals, not intrusive penetration testing."

That keeps risk low and still delivers real customer value.

## Feasibility Assessment
### 1. Technical Feasibility
- V1 Passive checks: Very high
- V2 Safe active checks: Medium to high
- V3 Deep dynamic testing: Medium (more engineering and legal controls)

### 2. Legal/Operational Feasibility
- High if scans are limited to user-provided domains and explicit user consent is required.
- Must include rate limits, robots/crawl policy controls, and abuse protection.

### 3. UX Feasibility
- High. Security findings can reuse your existing issue card model:
  - severity
  - evidence
  - recommendation
  - affected URLs

## Scope by Phase
### Phase V1 (Fast, High ROI, Safe)
Goal: Passive security posture checks from crawl/audit data.

Detect:
- Missing security headers:
  - Content-Security-Policy
  - Strict-Transport-Security
  - X-Frame-Options
  - X-Content-Type-Options
  - Referrer-Policy
  - Permissions-Policy
- Insecure transport patterns:
  - HTTP links from HTTPS pages (mixed content risk)
  - non-HTTPS canonical or asset references
- Cookie hygiene (response headers):
  - missing Secure
  - missing HttpOnly
  - missing SameSite
- Information leakage:
  - server/version banners
  - exposed stack traces or error signatures
  - sensitive keywords in HTML/JS
- Authentication posture signals:
  - login form without obvious CSRF token patterns
  - password fields on non-HTTPS pages

Outputs:
- Security score (0 to 100)
- Severity-bucketed findings (Critical, High, Medium, Low)
- Fix guidance with examples
- Evidence snapshots and header excerpts

Estimated effort:
- Backend + scoring + UI integration: 5 to 10 engineering days

### Phase V2 (Controlled Active Checks)
Goal: Add low-risk dynamic checks that do not exploit systems.

Detect:
- Reflected XSS indicators (safe payload reflection checks)
- Open redirect behavior (safe redirect probes)
- Basic SQLi pattern handling signals (error-based hints only)
- CORS misconfiguration patterns
- Directory listing exposure
- Weak cache controls on sensitive routes

Controls required:
- Explicit opt-in per scan
- Per-domain request budget
- Request throttle and timeout controls
- Blocklist for destructive methods (no PUT/PATCH/DELETE by default)

Estimated effort:
- 2 to 4 weeks depending on breadth and false-positive tuning

### Phase V3 (Advanced Security Intelligence)
Goal: Deep app-sec posture and enterprise value.

Add:
- Auth flow checks (session fixation indicators, logout invalidation signals)
- JWT/session token anti-pattern checks
- Client-side secret detection in JS bundles
- API endpoint surface discovery and risk tagging
- Historical drift and regression tracking for security posture
- Policy-as-code security baselines per organization

Estimated effort:
- 4 to 8+ weeks incremental, plus stronger governance and QA

## Proposed Architecture
### A. New Agent
- File: `backend/agents/security_agent.py`
- Responsibility:
  - consume crawl session data
  - run passive and optional active checks
  - produce normalized findings

### B. New Tools Module
- File: `backend/tools/security_scanner.py`
- Responsibilities:
  - header analysis
  - cookie directive analysis
  - safe payload probe utilities
  - evidence extraction helpers

### C. Data Model Extensions
Recommended tables:

1. `security_sessions`
- `id`
- `user_id`
- `crawl_session_id`
- `mode` (passive|active)
- `status`
- `started_at`
- `completed_at`
- `overall_score`

2. `security_findings`
- `id`
- `security_session_id`
- `page_id` (nullable)
- `category` (headers, cookies, xss, cors, transport, leakage, auth)
- `title`
- `description`
- `severity`
- `confidence`
- `evidence_json`
- `recommendation`
- `created_at`

3. `security_metrics`
- aggregated counters by severity/category for dashboards

### D. API Endpoints
Suggested endpoints:

- `POST /security/run`
  - body: crawl_session_id, mode, options
- `GET /security/session/{id}`
- `GET /security/session/{id}/findings`
- `GET /crawl/{id}/security` (load latest security session for a crawl)

### E. Frontend Integration
- Add a "Security" tab to existing analysis dashboard.
- Display:
  - score ring + severity counts
  - top exploitable findings first
  - affected pages and evidence snippets
  - one-click "Mark fixed" and "Re-verify"

## Scoring Model (Simple and Effective)
Start with weighted deductions:

- Critical: -20 each
- High: -10 each
- Medium: -4 each
- Low: -1 each

Then cap and normalize to [0, 100].

Optional weighting multipliers:
- page importance (home, pricing, auth, checkout)
- template spread (issue repeated across many pages)
- confidence score

## Risk and Guardrails
Must-have protections:

- Domain ownership control:
  - only scan target domain(s) user submitted
- Explicit user authorization checkbox before active checks
- Strict method policy (GET/HEAD default)
- Global and per-user rate limits
- Request timeout and retry ceilings
- Immutable audit logs for scan actions
- Abuse detection and temporary lockouts

## False Positives Strategy
- Add confidence per finding: High/Medium/Low
- Mark findings as "Needs verification" when heuristic confidence is low
- Allow user feedback: Confirmed / Not applicable / False positive
- Use feedback to tune rules over time

## MVP Recommendation (What to Build First)
Build V1 passive checks now.

Why:
- fastest to ship
- low legal and operational risk
- aligns perfectly with existing crawl pipeline
- immediately useful for users

MVP checklist:
- security agent and scanner module
- passive checks for headers/cookies/transport/leakage
- severity scoring + recommendations
- dashboard tab and endpoint loading
- exportable security summary

## Success Metrics
Track these after launch:

- adoption: % crawls with security run
- activation: % users opening Security tab
- remediation: % findings marked fixed
- re-audit improvement: score delta per project
- precision proxy: false-positive feedback rate

## Suggested 30-Day Plan
Week 1:
- implement data model + passive scanner rules
- add APIs and initial score model

Week 2:
- integrate frontend Security tab
- evidence rendering and export summary
- internal QA and tuning

Week 3:
- add opt-in controlled active checks (small set)
- add throttling and safety controls

Week 4:
- improve confidence model and prioritization
- rollout + monitor metrics

## Final Recommendation
Yes, you should build the Security Agent.

Best path:
1. Ship passive V1 quickly for real user value.
2. Add tightly controlled active checks in V2.
3. Expand to advanced security intelligence once feedback validates demand.

This approach gives strong product impact with controlled risk and predictable engineering effort.
