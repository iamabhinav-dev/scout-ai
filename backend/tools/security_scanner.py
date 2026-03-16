import re
from typing import Any, Dict, List
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

_STACK_TRACE_PATTERNS = [
    r"Traceback \(most recent call last\):",
    r"at\s+[\w$.<>]+\s*\(",
    r"Exception in thread",
    r"SQL syntax.*MySQL",
    r"Warning:\s+mysqli_",
    r"Fatal error:\s+Uncaught",
]

_SECRET_KEYWORDS = [
    "api_key",
    "secret_key",
    "aws_access_key_id",
    "private key",
    "authorization: bearer",
]


def _mk_finding(
    category: str,
    title: str,
    description: str,
    severity: str,
    confidence: str,
    recommendation: str,
    evidence: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "category": category,
        "title": title,
        "description": description,
        "severity": severity,
        "confidence": confidence,
        "recommendation": recommendation,
        "evidence": evidence,
    }


def fetch_page_with_headers(url: str, timeout: float = 15.0) -> Dict[str, Any]:
    headers = {"User-Agent": _UA}
    try:
        response = httpx.get(url, headers=headers, follow_redirects=True, timeout=timeout)
        return {
            "url": url,
            "final_url": str(response.url),
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "set_cookie": response.headers.get_list("set-cookie"),
            "raw_html": response.text,
            "error": None,
        }
    except Exception as exc:
        return {
            "url": url,
            "final_url": url,
            "status_code": None,
            "headers": {},
            "set_cookie": [],
            "raw_html": "",
            "error": str(exc),
        }


def _check_security_headers(url: str, final_url: str, headers: Dict[str, str]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    required = {
        "content-security-policy": ("high", "Set a strict Content-Security-Policy to reduce XSS injection risk."),
        "strict-transport-security": ("high", "Enable HSTS with a long max-age to enforce HTTPS."),
        "x-frame-options": ("medium", "Set X-Frame-Options to DENY or SAMEORIGIN to prevent clickjacking."),
        "x-content-type-options": ("medium", "Set X-Content-Type-Options to nosniff."),
        "referrer-policy": ("low", "Set a Referrer-Policy to minimize data leakage."),
        "permissions-policy": ("low", "Set a restrictive Permissions-Policy for browser features."),
    }

    lower = {k.lower(): v for k, v in headers.items()}
    is_https = final_url.lower().startswith("https://")

    for header, (severity, rec) in required.items():
        if header not in lower:
            # HSTS is only meaningful over HTTPS responses.
            if header == "strict-transport-security" and not is_https:
                continue
            findings.append(
                _mk_finding(
                    category="headers",
                    title=f"Missing {header}",
                    description=f"The response for {url} does not include {header}.",
                    severity=severity,
                    confidence="high",
                    recommendation=rec,
                    evidence={"url": url, "header": header},
                )
            )

    server = lower.get("server", "")
    if server and re.search(r"\d", server):
        findings.append(
            _mk_finding(
                category="leakage",
                title="Server version disclosure",
                description="Response exposes a versioned Server header.",
                severity="low",
                confidence="high",
                recommendation="Hide precise server/version details in production responses.",
                evidence={"url": url, "server": server},
            )
        )

    x_powered = lower.get("x-powered-by", "")
    if x_powered:
        findings.append(
            _mk_finding(
                category="leakage",
                title="Technology disclosure via X-Powered-By",
                description="Response reveals backend technology details in X-Powered-By.",
                severity="low",
                confidence="high",
                recommendation="Remove or sanitize X-Powered-By in production.",
                evidence={"url": url, "x_powered_by": x_powered},
            )
        )

    return findings


def _check_cookie_security(url: str, set_cookie_headers: List[str]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for raw_cookie in set_cookie_headers:
        cookie_lower = raw_cookie.lower()
        cookie_name = raw_cookie.split("=", 1)[0].strip() if "=" in raw_cookie else "unknown"

        if "secure" not in cookie_lower:
            findings.append(
                _mk_finding(
                    category="cookies",
                    title="Cookie missing Secure attribute",
                    description=f"Cookie {cookie_name} is set without the Secure attribute.",
                    severity="high",
                    confidence="high",
                    recommendation="Set Secure on cookies so they are only sent over HTTPS.",
                    evidence={"url": url, "cookie": cookie_name},
                )
            )
        if "httponly" not in cookie_lower:
            findings.append(
                _mk_finding(
                    category="cookies",
                    title="Cookie missing HttpOnly attribute",
                    description=f"Cookie {cookie_name} is set without HttpOnly.",
                    severity="high",
                    confidence="high",
                    recommendation="Set HttpOnly to reduce session theft risk via XSS.",
                    evidence={"url": url, "cookie": cookie_name},
                )
            )
        if "samesite" not in cookie_lower:
            findings.append(
                _mk_finding(
                    category="cookies",
                    title="Cookie missing SameSite attribute",
                    description=f"Cookie {cookie_name} is set without SameSite.",
                    severity="medium",
                    confidence="high",
                    recommendation="Set SameSite=Lax or Strict for CSRF resistance.",
                    evidence={"url": url, "cookie": cookie_name},
                )
            )
    return findings


def _check_transport_and_dom(url: str, final_url: str, raw_html: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    is_https = final_url.lower().startswith("https://")

    if not is_https:
        findings.append(
            _mk_finding(
                category="transport",
                title="Page served over HTTP",
                description="Final page URL is not HTTPS.",
                severity="high",
                confidence="high",
                recommendation="Redirect all traffic to HTTPS and enable HSTS.",
                evidence={"url": url, "final_url": final_url},
            )
        )

    if not raw_html:
        return findings

    soup = BeautifulSoup(raw_html, "html.parser")
    base_host = urlparse(final_url).netloc.lower()

    # Mixed-content style check for common asset tags.
    attrs = [
        ("script", "src"),
        ("img", "src"),
        ("iframe", "src"),
        ("link", "href"),
    ]
    for tag, attr in attrs:
        for node in soup.find_all(tag):
            val = node.get(attr)
            if not val:
                continue
            absolute = urljoin(final_url, val)
            if absolute.startswith("http://") and is_https:
                findings.append(
                    _mk_finding(
                        category="transport",
                        title="Mixed content reference",
                        description=f"HTTPS page references insecure asset: {absolute}",
                        severity="medium",
                        confidence="high",
                        recommendation="Serve all assets over HTTPS to avoid mixed-content risks.",
                        evidence={"url": url, "asset": absolute},
                    )
                )

    # Login form + CSRF hint heuristic.
    login_forms = 0
    csrf_forms = 0
    for form in soup.find_all("form"):
        form_text = " ".join((form.get_text(" ") or "").lower().split())
        form_html = str(form).lower()
        if "password" in form_html or any(k in form_text for k in ["sign in", "login", "log in"]):
            login_forms += 1
            if any(k in form_html for k in ["csrf", "_token", "xsrf"]):
                csrf_forms += 1

    if login_forms > 0 and csrf_forms == 0:
        findings.append(
            _mk_finding(
                category="auth",
                title="Login form without obvious CSRF token",
                description="Detected login/password form but no obvious CSRF token pattern.",
                severity="medium",
                confidence="medium",
                recommendation="Ensure anti-CSRF tokens are generated and validated on auth forms.",
                evidence={"url": url, "login_forms": login_forms},
            )
        )

    # Sensitive path leakage in links.
    sensitive_paths = ["/.env", "/config", "/backup", "/admin", "/.git"]
    found_paths = set()
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        absolute = urljoin(final_url, href)
        parsed = urlparse(absolute)
        if parsed.netloc.lower() != base_host:
            continue
        for p in sensitive_paths:
            if parsed.path.lower().startswith(p):
                found_paths.add(parsed.path)

    if found_paths:
        findings.append(
            _mk_finding(
                category="leakage",
                title="Potentially sensitive internal endpoints linked",
                description="Page links to endpoints that often expose sensitive internals.",
                severity="medium",
                confidence="medium",
                recommendation="Review and restrict sensitive endpoints from public navigation.",
                evidence={"url": url, "paths": sorted(found_paths)},
            )
        )

    # Error/secret signature scan.
    haystack = raw_html.lower()
    for pattern in _STACK_TRACE_PATTERNS:
        if re.search(pattern.lower(), haystack):
            findings.append(
                _mk_finding(
                    category="leakage",
                    title="Error stack trace signature found",
                    description="Page content appears to include a framework/runtime stack trace pattern.",
                    severity="high",
                    confidence="medium",
                    recommendation="Disable verbose error output in production responses.",
                    evidence={"url": url, "pattern": pattern},
                )
            )
            break

    for keyword in _SECRET_KEYWORDS:
        if keyword in haystack:
            findings.append(
                _mk_finding(
                    category="leakage",
                    title="Sensitive keyword pattern found in page source",
                    description="Page source contains a keyword commonly associated with secrets.",
                    severity="high",
                    confidence="low",
                    recommendation="Review and remove secrets from client-visible content and bundles.",
                    evidence={"url": url, "keyword": keyword},
                )
            )

    return findings


# ---------------------------------------------------------------------------
# Page-content-only checks (no HTTP fetch — uses already-scraped HTML)
# ---------------------------------------------------------------------------

def scan_page_content(url: str, final_url: str, raw_html: str) -> List[Dict[str, Any]]:
    """Run page-specific security checks that vary per page.

    Checks: mixed content, CSRF on login forms, sensitive paths linked,
    error/stack-trace signatures, secret keyword patterns.

    No HTTP request is made — *raw_html* should come from the crawler/scraper.
    """
    if not raw_html:
        return []

    findings: List[Dict[str, Any]] = []
    is_https = final_url.lower().startswith("https://")
    soup = BeautifulSoup(raw_html, "html.parser")
    base_host = urlparse(final_url).netloc.lower()

    # -- Mixed-content asset references
    attrs = [
        ("script", "src"),
        ("img", "src"),
        ("iframe", "src"),
        ("link", "href"),
    ]
    for tag, attr in attrs:
        for node in soup.find_all(tag):
            val = node.get(attr)
            if not val:
                continue
            absolute = urljoin(final_url, val)
            if absolute.startswith("http://") and is_https:
                findings.append(
                    _mk_finding(
                        category="transport",
                        title="Mixed content reference",
                        description=f"HTTPS page references insecure asset: {absolute}",
                        severity="medium",
                        confidence="high",
                        recommendation="Serve all assets over HTTPS to avoid mixed-content risks.",
                        evidence={"url": url, "asset": absolute},
                    )
                )

    # -- Login form + CSRF heuristic
    login_forms = 0
    csrf_forms = 0
    for form in soup.find_all("form"):
        form_text = " ".join((form.get_text(" ") or "").lower().split())
        form_html = str(form).lower()
        if "password" in form_html or any(k in form_text for k in ["sign in", "login", "log in"]):
            login_forms += 1
            if any(k in form_html for k in ["csrf", "_token", "xsrf"]):
                csrf_forms += 1

    if login_forms > 0 and csrf_forms == 0:
        findings.append(
            _mk_finding(
                category="auth",
                title="Login form without obvious CSRF token",
                description="Detected login/password form but no obvious CSRF token pattern.",
                severity="medium",
                confidence="medium",
                recommendation="Ensure anti-CSRF tokens are generated and validated on auth forms.",
                evidence={"url": url, "login_forms": login_forms},
            )
        )

    # -- Sensitive path leakage in links
    sensitive_paths = ["/.env", "/config", "/backup", "/admin", "/.git"]
    found_paths: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        absolute = urljoin(final_url, href)
        parsed = urlparse(absolute)
        if parsed.netloc.lower() != base_host:
            continue
        for p in sensitive_paths:
            if parsed.path.lower().startswith(p):
                found_paths.add(parsed.path)

    if found_paths:
        findings.append(
            _mk_finding(
                category="leakage",
                title="Potentially sensitive internal endpoints linked",
                description="Page links to endpoints that often expose sensitive internals.",
                severity="medium",
                confidence="medium",
                recommendation="Review and restrict sensitive endpoints from public navigation.",
                evidence={"url": url, "paths": sorted(found_paths)},
            )
        )

    # -- Error/secret signature scan
    haystack = raw_html.lower()
    for pattern in _STACK_TRACE_PATTERNS:
        if re.search(pattern.lower(), haystack):
            findings.append(
                _mk_finding(
                    category="leakage",
                    title="Error stack trace signature found",
                    description="Page content appears to include a framework/runtime stack trace pattern.",
                    severity="high",
                    confidence="medium",
                    recommendation="Disable verbose error output in production responses.",
                    evidence={"url": url, "pattern": pattern},
                )
            )
            break

    for keyword in _SECRET_KEYWORDS:
        if keyword in haystack:
            findings.append(
                _mk_finding(
                    category="leakage",
                    title="Sensitive keyword pattern found in page source",
                    description="Page source contains a keyword commonly associated with secrets.",
                    severity="high",
                    confidence="low",
                    recommendation="Review and remove secrets from client-visible content and bundles.",
                    evidence={"url": url, "keyword": keyword},
                )
            )

    return findings


# ---------------------------------------------------------------------------
# Site-wide scan (one HTTP fetch — headers, cookies, protocol, server info)
# ---------------------------------------------------------------------------

def scan_site_wide(url: str) -> Dict[str, Any]:
    """Run site-level passive security checks that are identical across pages.

    Performs one HTTP fetch and checks: security headers, cookie flags,
    transport protocol, and server/technology disclosure.
    """
    fetched = fetch_page_with_headers(url)
    if fetched.get("error"):
        return {
            "url": url,
            "status_code": fetched.get("status_code"),
            "error": fetched["error"],
            "findings": [
                _mk_finding(
                    category="availability",
                    title="Security scan fetch failed",
                    description="Could not fetch the page for passive security analysis.",
                    severity="low",
                    confidence="high",
                    recommendation="Verify URL accessibility and retry.",
                    evidence={"url": url, "error": fetched["error"]},
                )
            ],
        }

    final_url = fetched["final_url"]
    headers = fetched["headers"]
    set_cookie = fetched["set_cookie"]

    findings: List[Dict[str, Any]] = []
    findings.extend(_check_security_headers(url, final_url, headers))
    findings.extend(_check_cookie_security(url, set_cookie))

    # Transport-level check (HTTP vs HTTPS) — same for whole site
    is_https = final_url.lower().startswith("https://")
    if not is_https:
        findings.append(
            _mk_finding(
                category="transport",
                title="Page served over HTTP",
                description="Final page URL is not HTTPS.",
                severity="high",
                confidence="high",
                recommendation="Redirect all traffic to HTTPS and enable HSTS.",
                evidence={"url": url, "final_url": final_url},
            )
        )

    return {
        "url": url,
        "final_url": final_url,
        "status_code": fetched.get("status_code"),
        "headers": headers,
        "findings": findings,
    }


# ---------------------------------------------------------------------------
# Combined scan (original — kept for single-page /audit endpoint)
# ---------------------------------------------------------------------------

def scan_url_passive(url: str) -> Dict[str, Any]:
    """Run ALL passive security checks for one URL and return normalized findings."""
    fetched = fetch_page_with_headers(url)
    if fetched.get("error"):
        return {
            "url": url,
            "status_code": fetched.get("status_code"),
            "error": fetched["error"],
            "findings": [
                _mk_finding(
                    category="availability",
                    title="Security scan fetch failed",
                    description="Could not fetch the page for passive security analysis.",
                    severity="low",
                    confidence="high",
                    recommendation="Verify URL accessibility and retry.",
                    evidence={"url": url, "error": fetched["error"]},
                )
            ],
        }

    final_url = fetched["final_url"]
    headers = fetched["headers"]
    raw_html = fetched["raw_html"]
    set_cookie = fetched["set_cookie"]

    findings: List[Dict[str, Any]] = []
    findings.extend(_check_security_headers(url, final_url, headers))
    findings.extend(_check_cookie_security(url, set_cookie))
    findings.extend(_check_transport_and_dom(url, final_url, raw_html))

    return {
        "url": url,
        "final_url": final_url,
        "status_code": fetched.get("status_code"),
        "headers": headers,
        "findings": findings,
    }
