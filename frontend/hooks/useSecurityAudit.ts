"use client";

import { useEffect, useRef, useState } from "react";

export type SecurityAuditStatus = "idle" | "running" | "complete" | "failed";

export interface SecurityFinding {
  id: string;
  page_id: string | null;
  url: string;
  category: string;
  title: string;
  description: string;
  severity: "critical" | "high" | "medium" | "low" | string;
  confidence: "high" | "medium" | "low" | string;
  recommendation: string;
  evidence_json: Record<string, unknown> | null;
  created_at: string;
}

export interface SecuritySession {
  id: string;
  crawl_session_id: string;
  mode: string;
  status: string;
  overall_score: number | null;
  scanned_pages: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  started_at: string;
  completed_at: string | null;
}

export interface SecurityAuditResult {
  status: SecurityAuditStatus;
  securitySession: SecuritySession | null;
  findings: SecurityFinding[];
  error: string | null;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function useSecurityAudit(
  crawlSessionId: string | null,
  enabled: boolean,
  accessToken?: string | null,
  existingCrawlSessionId?: string,
): SecurityAuditResult {
  const [status, setStatus] = useState<SecurityAuditStatus>("idle");
  const [securitySession, setSecuritySession] = useState<SecuritySession | null>(null);
  const [findings, setFindings] = useState<SecurityFinding[]>([]);
  const [error, setError] = useState<string | null>(null);

  const lastRunForSessionRef = useRef<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const sessionToUse = existingCrawlSessionId ?? crawlSessionId;
    if (!sessionToUse) {
      abortRef.current?.abort();
      setStatus("idle");
      setSecuritySession(null);
      setFindings([]);
      setError(null);
      return;
    }

    const controller = new AbortController();
    abortRef.current = controller;

    async function loadLatest() {
      const headers: Record<string, string> = {};
      if (accessToken) headers.Authorization = `Bearer ${accessToken}`;

      const res = await fetch(`${API_URL}/crawl/${sessionToUse}/security`, {
        headers,
        signal: controller.signal,
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);

      const session = (data.security_session ?? null) as SecuritySession | null;
      const findingsData = (data.findings ?? []) as SecurityFinding[];

      setSecuritySession(session);
      setFindings(findingsData);
      setStatus(session ? "complete" : "idle");
      setError(null);
    }

    async function runAndLoad() {
      try {
        if (existingCrawlSessionId) {
          setStatus("running");
          await loadLatest();
          return;
        }

        if (!enabled) {
          setStatus("idle");
          return;
        }

        // Avoid duplicate POST runs for the same crawl session in one dashboard lifecycle.
        if (lastRunForSessionRef.current === sessionToUse) {
          setStatus("running");
          await loadLatest();
          return;
        }

        setStatus("running");
        const headers: Record<string, string> = { "Content-Type": "application/json" };
        if (accessToken) headers.Authorization = `Bearer ${accessToken}`;

        const runRes = await fetch(`${API_URL}/security/run`, {
          method: "POST",
          headers,
          body: JSON.stringify({
            crawl_session_id: sessionToUse,
            mode: "passive",
            page_limit: 500,
          }),
          signal: controller.signal,
        });
        const runData = await runRes.json();
        if (!runRes.ok || runData.error) {
          throw new Error(runData.error || `Security run failed with HTTP ${runRes.status}`);
        }

        lastRunForSessionRef.current = sessionToUse;
        await loadLatest();
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") return;
        setError(err instanceof Error ? err.message : String(err));
        setStatus("failed");
      }
    }

    runAndLoad();
    return () => controller.abort();
  }, [crawlSessionId, enabled, accessToken, existingCrawlSessionId]);

  return { status, securitySession, findings, error };
}
