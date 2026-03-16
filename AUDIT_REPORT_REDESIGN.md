# Audit Report UI Redesign Plan

## Problems with the Current Design

### 1. Score Scale Mismatch
- The reports from all four agents use a **1–10 scale** (e.g. `overall_score: 7.2`)
- The compliance report uses a **1–10 risk scale** (lower is better)
- The current dashboard multiplies scores by 10 to produce a 0–100 number for the circular gauge and score bars
- The SiteAuditResults table displays raw 1–10 values with its own colour thresholds (≥7.5 green, ≥5 amber, else red)
- These two representations are inconsistent — the same score looks different depending on which UI you are reading
- **Fix:** Standardise on the native 1–10 scale everywhere. Drop the ×10 conversion. Update all thresholds and labels to match.

### 2. "Active Agents" Section
- The animated agent cards with progress bars and fake terminal lines are a loading-time gimmick
- They persist and remain visible after the audit is complete, taking up a full section of vertical space
- When the page is opened in read-only / pre-loaded mode (coming back from the crawler dashboard), the agents never actually ran — yet the animation plays anyway
- **Fix:** Remove the Active Agents section entirely. Replace with a minimal inline loading state (skeleton or spinner) that disappears once results are ready.

### 3. Layout Issues
- The tabbed layout (Overall / UI / UX / Compliance / SEO) forces the user to click through each agent one at a time to read findings
- Switching tabs discards context — you cannot compare findings across agents without tabbing back and forth
- The overall tab's "Priority Actions" mixes recommendations from all agents in a flat list with no grouping
- The "Executive Summary" is a concatenated string of all agent findings — it reads like debug output, not a useful summary
- The circular gauges look good but convey no new information beyond the number inside them
- The detailed checks panel (pass/fail list) and the insights panel duplicate information that is already implicit in the score

---

## Proposed New Layout

### Principles
- **Single scroll, no tabs.** Show all four agents at once in a scannable layout.
- **1–10 scale throughout.** Match the scale used in the crawler audit table.
- **Findings first.** The most actionable content (recommendations, failed checks) should be prominent, not buried.
- **No fake activity.** Loading state is a clean skeleton. No animated agents post-completion.

---

### Page Structure

```
┌─────────────────────────────────────────────────────────┐
│  ← Back   [URL pill]           Audit Report   [status]  │  ← Sticky header
└─────────────────────────────────────────────────────────┘

┌──── Score Summary Bar ──────────────────────────────────┐
│  UI  7.4 ████████░░  │  UX  6.1 ██████░░░░  │  ...    │
│  SEO 8.0 ████████░░  │  Risk 3/10 (low)     │          │
└─────────────────────────────────────────────────────────┘

┌──── Priority Recommendations ───────────────────────────┐
│  Grouped by source: Critical violations → High → Medium │
│  Each item: [badge] [agent tag] recommendation text      │
└─────────────────────────────────────────────────────────┘

┌──── UI Agent ─────────────┐  ┌──── UX Agent ────────────┐
│  Score: 7.4 / 10          │  │  Score: 6.1 / 10          │
│  ─────────────────────    │  │  ─────────────────────    │
│  Layout & spacing  8.0    │  │  Accessibility     5.5    │
│  Responsiveness    7.0    │  │  UX friction       6.5    │
│  Typography        6.8    │  │  Navigation & IA   7.0    │
│  Color coherence   7.8    │  │  Inclusivity       5.5    │
│  ─────────────────────    │  │  ─────────────────────    │
│  Findings (4 items)       │  │  Findings (4 items)       │
│  [expandable per sub-cat] │  │  [expandable per sub-cat] │
└───────────────────────────┘  └───────────────────────────┘

┌──── SEO Agent ────────────┐  ┌──── Compliance Agent ─────┐
│  Score: 8.0 / 10          │  │  Risk: 3 / 10 (Low)        │
│  Universal factors list   │  │  Data privacy: Low         │
│  pass/fail/warn per item  │  │  Legal transparency: Med   │
│  ─────────────────────    │  │  A11y compliance: Low      │
│  Intent alignment: good   │  │  ─────────────────────    │
│  Missing entities: ...    │  │  Critical violations list  │
└───────────────────────────┘  └───────────────────────────┘
```

---

### Component Breakdown

#### `AuditScoreSummaryBar`
- Horizontal bar at the top showing all four scores side by side
- Each score: agent name + numeric score + filled bar on 1–10 scale
- Colour thresholds: ≥7.5 green, ≥5 amber, <5 red (matching SiteAuditResults table)
- Compliance shown as "Risk X/10" with inverted colour (low risk = green)
- No circular gauges — they add visual weight without adding information

#### `PriorityRecommendations`
- Replaces the current "Priority Actions" and "Executive Summary"
- Sections: Critical (compliance violations) → High (UI/UX recs) → Medium (SEO recs)
- Each item shows an agent tag badge (e.g. `[UI]`, `[SEO]`) so source is clear
- Max 8–10 items, sorted by severity

#### `AgentCard` (×4, rendered in a 2-col grid)
- **Header:** agent name + numeric score pill
- **Sub-scores table:** each category with its 1–10 score and a thin fill bar
- **Findings section:** the `findings` text per category, shown as plain readable paragraphs
- For SEO: universal factors as pass/warn/fail rows; intent alignment and missing entities as text
- For Compliance: risk level per category + critical violations list
- No expandable/collapsible needed — all content visible by default

#### Loading State
- Skeleton version of the score summary bar and four agent cards
- No animated progress bars or fake terminal lines

#### Header
- Sticky top bar: back button, URL pill, "Audit Report" title, Ready / Processing badge
- Remove the large heading "AI Analysis Dashboard"

---

## Scoring Conventions (Unified)

| Agent       | Field               | Display               | Green  | Amber  | Red   |
|-------------|---------------------|-----------------------|--------|--------|-------|
| UI          | `overall_score`     | X.X / 10             | ≥ 7.5  | ≥ 5.0  | < 5.0 |
| UX          | `overall_score`     | X.X / 10             | ≥ 7.5  | ≥ 5.0  | < 5.0 |
| SEO         | `overall_score`     | X.X / 10             | ≥ 7.5  | ≥ 5.0  | < 5.0 |
| Compliance  | `overall_risk_score`| Risk X / 10 (inverted)| ≤ 3.0  | ≤ 6.0  | > 6.0 |

Sub-category scores use the same thresholds.

---

## Files to Change

| File | Change |
|------|--------|
| `frontend/components/nonprimitive/AnalysisDashboard.tsx` | Full rewrite with new layout |
| `frontend/components/nonprimitive/SiteAuditResults.tsx` | Already uses 1–10 (no change needed to score logic) |
| `frontend/hooks/useAuditStream.ts` | No changes — types are already correct |

---

## What Gets Removed

- `AgentIcon` component
- `AGENTS`, `AGENT_MESSAGES`, `AgentState`, `AgentStatus` types
- `agentStates` state + all `setInterval` animation logic
- `CircularGauge` and `ScoreBar` components
- `scoreFromRisk` ×10 conversion helper
- Tabbed navigation (Overall / UI / UX / Compliance / SEO)
- `activeTab` state and all tab-switching logic
- `summaries` memo (concatenated string summaries)
- The skeleton placeholder section (replaced with per-card skeletons)
