import os
import re
import json
import time
import logging

from gradient import Gradient
from gradient import APITimeoutError, APIConnectionError

log = logging.getLogger("scout")

_SYSTEM_PROMPT = """You are a strict Regulatory, Data Privacy, and Accessibility Compliance Auditor for Scout.ai.
Your role is to identify legal liabilities and regulatory violations (GDPR, CCPA, WCAG 2.1, ADA).
Score overall_risk_score from 1 (critical legal risk / non-compliant) to 10 (fully compliant).
Respond with valid JSON only — no markdown, no extra text."""

_MODEL = "llama3.3-70b-instruct"
_MAX_RETRIES = 3
_RETRY_DELAY = 3  # seconds

_JSON_SCHEMA = """
Return ONLY this JSON structure (no markdown):
{
  "overall_risk_score": <integer 1-10>,
  "data_privacy": {
    "risk_level": "<High|Medium|Low>",
    "findings": "<observations about cookie banners, consent forms, PII collection>"
  },
  "legal_transparency": {
    "risk_level": "<High|Medium|Low>",
    "findings": "<observations about ToS, Privacy Policy links, company info>"
  },
  "accessibility_compliance": {
    "risk_level": "<High|Medium|Low>",
    "findings": "<observations based on the DOM and accessibility_summary>"
  },
  "critical_violations": ["<immediate legal/regulatory liability>", ...]
}
"""


def run_compliance_audit(url: str, context: dict) -> dict:
    """Produce a scored legal & compliance audit using Llama 3.3 70B via Gradient."""
    if context.get("error"):
        return {"error": context["error"]}

    summary = context["accessibility_summary"]
    dom_snippet = context["dom"][:8000]

    text_prompt = f"""Perform a strict legal and compliance audit on: {url}

ACCESSIBILITY SUMMARY:
- Total images: {summary['images_total']}, missing alt text: {summary['images_missing_alt']}
- Heading hierarchy: {summary['heading_hierarchy']}
- Total form inputs: {summary['total_inputs']}, labeled: {summary['labeled_inputs']}
- ARIA roles present: {summary['aria_roles_found']}

DOM CONTENT (first 8000 chars):
{dom_snippet}

AUDIT INSTRUCTIONS:
1. Data Privacy: Check for the presence and adequacy of cookie consent banners, GDPR/CCPA opt-in checkboxes on forms, and any unconsented PII collection fields (email, phone, address). Flag pre-ticked consent boxes as dark patterns.
2. Legal Transparency: Verify that Privacy Policy and Terms of Service links are present and functional. Flag any anchor tags with href="#" that appear to be placeholder legal links. Check for visible company name, registration number, or contact address.
3. Accessibility Compliance (WCAG 2.1 / ADA): Use the accessibility summary above to identify failures — missing alt text on images, unlabeled form inputs, and broken heading hierarchy are potential ADA/WCAG violations.
4. Dark Patterns: Scan the DOM for manipulative UI patterns such as hidden unsubscribe options, misleading button labels, forced continuity, or obscured cancellation flows.

{_JSON_SCHEMA}"""

    client = Gradient(
        model_access_key=os.environ.get("DIGITALOCEAN_INFERENCE_KEY"),
        timeout=120.0,
    )

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": text_prompt},
                ],
                model=_MODEL,
            )
            raw = response.choices[0].message.content
            match = re.search(r"\{[\s\S]*\}", raw)
            if match:
                return json.loads(match.group())
            return {"error": "Failed to parse compliance report", "raw": raw}

        except (APITimeoutError, APIConnectionError) as exc:
            if attempt < _MAX_RETRIES:
                log.warning("[compliance_auditor] attempt %d/%d failed (%s) — retrying in %ds",
                            attempt, _MAX_RETRIES, type(exc).__name__, _RETRY_DELAY)
                time.sleep(_RETRY_DELAY)
            else:
                log.error("[compliance_auditor] all %d attempts failed: %s", _MAX_RETRIES, exc)
                return {"error": f"Gradient API unreachable after {_MAX_RETRIES} attempts: {exc}"}
