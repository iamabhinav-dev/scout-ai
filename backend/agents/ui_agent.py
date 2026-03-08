import os
import base64
import json

from google import genai
from google.genai import types

_SYSTEM_PROMPT = """You are a Senior UI Engineer and Visual Design Critic for Scout.ai.
Score each area from 1 (broken) to 10 (excellent).
Respond with valid JSON only — no markdown, no extra text."""

_MODEL = "gemini-2.5-flash"

_JSON_SCHEMA = """
Return ONLY this JSON structure:
{
  "overall_score": <integer 1-10>,
  "layout_spacing":  { "score": <integer 1-10>, "findings": "<observations>" },
  "responsiveness":  { "score": <integer 1-10>, "findings": "<observations>" },
  "typography":      { "score": <integer 1-10>, "findings": "<observations>" },
  "color_coherence": { "score": <integer 1-10>, "findings": "<observations>" },
  "recommendations": ["<actionable fix>", ...]
}
"""


def run_ui_audit(url: str, context: dict) -> dict:
    """Produce a scored UI audit using Gemini 2.5 Flash with vision."""
    if context.get("error"):
        return {"error": context["error"]}

    summary = context["accessibility_summary"]
    dom_snippet = context["dom"][:6000]
    screenshot_b64 = context.get("screenshot_base64")

    text_prompt = f"""Perform a UI (visual design & layout) audit on: {url}

PAGE SIGNALS:
- Has viewport meta tag: {summary['has_viewport_meta']}
- Heading hierarchy: {summary['heading_hierarchy']}

DOM CONTENT (first 6000 chars):
{dom_snippet}

{_JSON_SCHEMA}"""

    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

    parts = []
    if screenshot_b64:
        parts.append(types.Part.from_bytes(
            data=base64.b64decode(screenshot_b64),
            mime_type="image/png",
        ))
    parts.append(types.Part.from_text(text=text_prompt))

    response = client.models.generate_content(
        model=_MODEL,
        contents=[types.Content(role="user", parts=parts)],
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
            response_mime_type="application/json",
        ),
    )
    return json.loads(response.text)
