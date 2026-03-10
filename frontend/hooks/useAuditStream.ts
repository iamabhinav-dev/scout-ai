"use client";

import { useEffect, useState } from "react";

// ---------------------------------------------------------------------------
// Types — mirror the backend JSON schemas exactly
// ---------------------------------------------------------------------------

export interface AuditCategory {
  score: number;       // 1–10
  findings: string;
}

export interface UiReport {
  overall_score: number;
  layout_spacing: AuditCategory;
  responsiveness: AuditCategory;
  typography: AuditCategory;
  color_coherence: AuditCategory;
  recommendations: string[];
  error?: string;
}

export interface UxReport {
  overall_score: number;
  accessibility: AuditCategory;
  ux_friction: AuditCategory;
  navigation_ia: AuditCategory;
  inclusivity: AuditCategory;
  recommendations: string[];
  error?: string;
}

// ---------------------------------------------------------------------------
// SSE event shapes from backend
// ---------------------------------------------------------------------------

type SseUiResultEvent  = { type: "ui_result"; ui_report: UiReport };
type SseUxResultEvent  = { type: "ux_result"; ux_report: UxReport };
type SseResultEvent    = { type: "result"; ui_report: UiReport; ux_report: UxReport };
type SseErrorEvent     = { type: "error"; message: string };

type SseEvent =
  | { type: "status"; [key: string]: unknown }  // ignored
  | SseUiResultEvent
  | SseUxResultEvent
  | SseResultEvent
  | SseErrorEvent;

// ---------------------------------------------------------------------------
// Public hook return type
// ---------------------------------------------------------------------------

export interface AuditStreamResult {
  uiReport: UiReport | null;
  uxReport: UxReport | null;
  isLoading: boolean;
  /** Final `type: "result"` received — both reports are populated */
  isDone: boolean;
  error: string | null;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function useAuditStream(targetUrl: string): AuditStreamResult {
  const [uiReport, setUiReport]   = useState<UiReport | null>(null);
  const [uxReport, setUxReport]   = useState<UxReport | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isDone, setIsDone]       = useState(false);
  const [error, setError]         = useState<string | null>(null);

  useEffect(() => {
    if (!targetUrl) return;

    // Reset state so a re-run (e.g. React Strict Mode double-invoke) starts clean
    setUiReport(null);
    setUxReport(null);
    setIsLoading(false);
    setIsDone(false);
    setError(null);

    const abortController = new AbortController();

    async function stream() {
      setIsLoading(true);

      try {
        const response = await fetch(`${API_URL}/audit`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url: targetUrl }),
          signal: abortController.signal,
        });

        if (!response.ok) {
          const text = await response.text();
          throw new Error(`HTTP ${response.status}: ${text}`);
        }

        if (!response.body) {
          throw new Error("No response body — streaming not supported");
        }

        const reader  = response.body.getReader();
        const decoder = new TextDecoder();
        let   buffer  = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // SSE messages are separated by double newlines
          const parts = buffer.split("\n\n");
          // Keep the last incomplete chunk in the buffer
          buffer = parts.pop() ?? "";

          for (const part of parts) {
            const line = part.trim();
            if (!line.startsWith("data:")) continue;

            const jsonStr = line.slice("data:".length).trim();
            if (!jsonStr) continue;

            let event: SseEvent;
            try {
              event = JSON.parse(jsonStr) as SseEvent;
            } catch {
              console.warn("[useAuditStream] Failed to parse SSE chunk:", jsonStr);
              continue;
            }

            handleEvent(event);
          }
        }
      } catch (err: unknown) {
        if (err instanceof Error && err.name === "AbortError") return;
        const msg = err instanceof Error ? err.message : String(err);
        setError(msg);
        setIsLoading(false);
      }
    }

    function handleEvent(event: SseEvent) {
      switch (event.type) {
        case "status":
          // Agent card animations are fully mocked — ignore status events
          break;

        case "ui_result":
          setUiReport(event.ui_report);
          break;

        case "ux_result":
          setUxReport(event.ux_report);
          break;

        case "result":
          if (event.ui_report) setUiReport(event.ui_report);
          if (event.ux_report) setUxReport(event.ux_report);
          setIsLoading(false);
          setIsDone(true);
          break;

        case "error":
          setError(event.message);
          setIsLoading(false);
          break;
      }
    }

    stream();

    return () => {
      abortController.abort();
    };
  }, [targetUrl]);

  return { uiReport, uxReport, isLoading, isDone, error };
}
