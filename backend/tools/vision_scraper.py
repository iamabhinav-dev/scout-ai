import base64
from html.parser import HTMLParser

import httpx
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright


class _AccessibilityChecker(HTMLParser):
    """Lightweight HTML parser to extract accessibility signals from rendered DOM."""

    def __init__(self):
        super().__init__()
        self.img_total = 0
        self.img_missing_alt = 0
        self.headings = []
        self.total_inputs = 0
        self.labeled_inputs = 0
        self.aria_roles = []
        self.has_viewport_meta = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        if tag == "img":
            self.img_total += 1
            alt = attrs_dict.get("alt")
            if alt is None or alt.strip() == "":
                self.img_missing_alt += 1

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.headings.append(tag)

        if tag == "meta" and attrs_dict.get("name", "").lower() == "viewport":
            self.has_viewport_meta = True

        if tag == "input" and attrs_dict.get("type", "text") not in (
            "hidden",
            "submit",
            "button",
            "image",
        ):
            self.total_inputs += 1
            if (
                "aria-label" in attrs_dict
                or "aria-labelledby" in attrs_dict
                or "id" in attrs_dict
            ):
                self.labeled_inputs += 1

        role = attrs_dict.get("role")
        if role:
            self.aria_roles.append(role)


def capture_website_context(url: str, viewport_width: int = 1280, viewport_height: int = 800) -> dict:
    """Use a headless Chromium browser to render a page and return its context.

    Returns a dict with keys:
        url, dom, screenshot_base64, accessibility_summary, final_url
    On error the dict will have an 'error' key instead.
    """
    html = ""
    screenshot_base64 = None
    final_url = url

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                viewport={"width": viewport_width, "height": viewport_height},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
            except PlaywrightTimeoutError:
                # Page timed out waiting for domcontentloaded, but content may
                # already be present — proceed and grab whatever loaded.
                pass

            final_url = page.url
            html = page.content()
            screenshot_bytes = page.screenshot(full_page=True)
            screenshot_base64 = base64.b64encode(screenshot_bytes).decode("utf-8")
            browser.close()

    except Exception as exc:
        # Playwright failed entirely — fall back to a plain HTTP fetch
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            }
            resp = httpx.get(url, headers=headers, follow_redirects=True, timeout=30)
            html = resp.text
            final_url = str(resp.url)
        except Exception as http_exc:
            return {
                "url": url,
                "error": f"Playwright: {exc} | HTTP fallback: {http_exc}",
                "dom": "",
                "screenshot_base64": None,
                "accessibility_summary": {},
            }

    checker = _AccessibilityChecker()
    checker.feed(html)

    accessibility_summary = {
        "images_total": checker.img_total,
        "images_missing_alt": checker.img_missing_alt,
        "heading_hierarchy": checker.headings,
        "has_viewport_meta": checker.has_viewport_meta,
        "total_inputs": checker.total_inputs,
        "labeled_inputs": checker.labeled_inputs,
        "aria_roles_found": list(set(checker.aria_roles)),
    }

    return {
        "url": url,
        "dom": html,
        "screenshot_base64": screenshot_base64,
        "accessibility_summary": accessibility_summary,
        "final_url": final_url,
    }
