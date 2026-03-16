from typing import Any, Dict, List, Optional

from tools.security_scanner import scan_url_passive, scan_site_wide, scan_page_content


_SEVERITY_WEIGHT = {
    "critical": 20,
    "high": 10,
    "medium": 4,
    "low": 1,
}


def _compute_overall_score(findings: List[Dict[str, Any]]) -> int:
    penalty = 0
    for finding in findings:
        sev = str(finding.get("severity", "low")).lower()
        penalty += _SEVERITY_WEIGHT.get(sev, 1)
    score = max(0, 100 - penalty)
    return int(score)


def _summary(findings: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for finding in findings:
        sev = str(finding.get("severity", "low")).lower()
        if sev in counts:
            counts[sev] += 1
        else:
            counts["low"] += 1
    return counts


def run_security_audit(
    urls: List[str],
    mode: str = "passive",
    page_id_by_url: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Run Phase 1 security audit (passive mode) and return normalized results."""
    if mode != "passive":
        return {
            "error": "Only passive mode is supported in Phase 1",
            "mode": mode,
            "overall_score": 0,
            "counts": {"critical": 0, "high": 0, "medium": 0, "low": 0},
            "findings": [],
        }

    all_findings: List[Dict[str, Any]] = []

    seen = set()
    unique_urls = []
    for raw in urls:
        url = (raw or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        unique_urls.append(url)

    for url in unique_urls:
        page_result = scan_url_passive(url)
        page_findings = page_result.get("findings", [])
        for finding in page_findings:
            enriched = {
                **finding,
                "url": url,
                "page_id": (page_id_by_url or {}).get(url),
            }
            all_findings.append(enriched)

    counts = _summary(all_findings)
    overall_score = _compute_overall_score(all_findings)

    return {
        "mode": mode,
        "overall_score": overall_score,
        "counts": counts,
        "findings": all_findings,
        "scanned_pages": len(unique_urls),
    }


# ---------------------------------------------------------------------------
# Site-wide security audit  (run once on root URL)
# ---------------------------------------------------------------------------

def run_site_wide_security_audit(root_url: str) -> Dict[str, Any]:
    """Fetch the root URL once and run only site-level checks.

    Returns { overall_score, counts, findings, mode }.
    """
    result = scan_site_wide(root_url)
    findings = result.get("findings", [])
    # Tag every finding with scope for downstream persistence
    for f in findings:
        f["scope"] = "site_wide"
        f.setdefault("url", root_url)

    counts = _summary(findings)
    overall_score = _compute_overall_score(findings)

    return {
        "mode": "passive/site-wide",
        "overall_score": overall_score,
        "counts": counts,
        "findings": findings,
    }


# ---------------------------------------------------------------------------
# Per-page content security check  (no HTTP fetch)
# ---------------------------------------------------------------------------

def run_page_content_security_check(
    url: str,
    final_url: str,
    raw_html: str,
) -> Dict[str, Any]:
    """Run page-specific content checks using already-fetched HTML.

    Returns { findings }.  No aggregate score — these are merged into the
    site-wide score later.
    """
    findings = scan_page_content(url, final_url, raw_html)
    for f in findings:
        f["scope"] = "page_content"
        f.setdefault("url", url)

    return {"findings": findings}
