import asyncio
import json
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv()

from agents.ui_agent import run_ui_audit
from agents.ux_agent import run_ux_audit
from tools.vision_scraper import capture_website_context

app = FastAPI(title="Scout.ai")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AuditRequest(BaseModel):
    url: str


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


async def _stream_audit(url: str):
    loop = asyncio.get_event_loop()
    try:
        yield _sse({"type": "status", "step": "fetch", "message": "🌐 Fetching page context..."})
        context = await loop.run_in_executor(None, capture_website_context, url)

        if context.get("error"):
            yield _sse({"type": "error", "message": context["error"]})
            return

        yield _sse({"type": "status", "step": "ui", "message": "🎨 Running UI audit (Gemini 2.5 Flash + vision)..."})
        ui_report = await loop.run_in_executor(None, run_ui_audit, url, context)

        yield _sse({"type": "status", "step": "ux", "message": "🧭 Running UX audit (Llama 3.3 70B via Gradient)..."})
        ux_report = await loop.run_in_executor(None, run_ux_audit, url, context)

        yield _sse({"type": "result", "ui_report": ui_report, "ux_report": ux_report})

    except Exception as exc:
        yield _sse({"type": "error", "message": str(exc)})


@app.post("/audit")
async def audit(req: AuditRequest):
    return StreamingResponse(
        _stream_audit(req.url),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )