"use client";

import { useMemo } from "react";
import type {
  AuditStatus,
  PageAuditResult,
  SiteSecurityReport,
} from "@/hooks/useSiteAuditStream";

interface Props {
  siteReport: SiteSecurityReport | null;
  pageAudits: Map<string, PageAuditResult>;
  auditStatus: AuditStatus;
}

/* eslint-disable @typescript-eslint/no-explicit-any */
interface Finding {
  severity: string;
  confidence: string;
  category: string;
  title: string;
  description: string;
  url: string;
  recommendation: string;
  scope: string;
}

function severityClass(sev: string): string {
  const s = sev.toLowerCase();
  if (s === "critical") return "bg-red-500/20 text-red-300 border-red-500/30";
  if (s === "high") return "bg-orange-500/20 text-orange-300 border-orange-500/30";
  if (s === "medium") return "bg-amber-500/20 text-amber-300 border-amber-500/30";
  return "bg-blue-500/20 text-blue-300 border-blue-500/30";
}

function confidenceClass(conf: string): string {
  const c = conf.toLowerCase();
  if (c === "high") return "text-emerald-300";
  if (c === "medium") return "text-amber-300";
  return "text-zinc-400";
}

function pathOnly(url: string): string {
  try {
    const p = new URL(url);
    return `${p.pathname || "/"}${p.search || ""}`;
  } catch {
    return url;
  }
}

function asFinding(raw: Record<string, any>, scope: string): Finding {
  return {
    severity:       raw.severity       ?? "low",
    confidence:     raw.confidence     ?? "low",
    category:       raw.category       ?? "",
    title:          raw.title          ?? "",
    description:    raw.description    ?? "",
    url:            raw.url            ?? "",
    recommendation: raw.recommendation ?? "",
    scope,
  };
}

function FindingsTable({ findings, label }: { findings: Finding[]; label: string }) {
  if (findings.length === 0) return null;

  return (
    <div className="mb-6">
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-zinc-400">{label}</h3>
      <div className="rounded-xl border border-white/10 overflow-hidden">
        <div className="max-h-96 overflow-auto">
          <table className="w-full border-collapse text-sm">
            <thead className="sticky top-0 z-10">
              <tr className="border-b border-white/10 bg-zinc-900">
                <th className="py-2.5 pl-4 pr-2 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">Severity</th>
                <th className="py-2.5 pr-2 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">Category</th>
                <th className="py-2.5 pr-2 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">Issue</th>
                <th className="py-2.5 pr-2 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">Page</th>
                <th className="py-2.5 pr-4 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">Recommendation</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {findings.map((f, i) => (
                <tr key={`${f.scope}-${f.url}-${f.title}-${i}`} className="hover:bg-white/3 transition-colors align-top">
                  <td className="py-3 pl-4 pr-2">
                    <span className={`rounded border px-2 py-0.5 text-xs font-semibold uppercase ${severityClass(f.severity)}`}>
                      {f.severity}
                    </span>
                    <p className={`mt-1 text-[11px] ${confidenceClass(f.confidence)}`}>{f.confidence} confidence</p>
                  </td>
                  <td className="py-3 pr-2 text-xs text-zinc-300 capitalize">{f.category}</td>
                  <td className="py-3 pr-2">
                    <p className="text-xs font-semibold text-zinc-100">{f.title}</p>
                    <p className="mt-1 text-xs text-zinc-400 max-w-xl">{f.description}</p>
                  </td>
                  <td className="py-3 pr-2 text-xs font-mono text-zinc-300 max-w-xs truncate" title={f.url}>
                    {f.scope === "site_wide" ? (
                      <span className="text-indigo-400">🌐 Site-wide</span>
                    ) : (
                      pathOnly(f.url)
                    )}
                  </td>
                  <td className="py-3 pr-4 text-xs text-zinc-300 max-w-md">{f.recommendation}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default function SecurityAuditResults({ siteReport, pageAudits, auditStatus }: Props) {
  const siteFindings = useMemo(
    () => (siteReport?.site_wide_findings ?? []).map((r) => asFinding(r, "site_wide")),
    [siteReport],
  );

  const pageFindings = useMemo(() => {
    const out: Finding[] = [];
    for (const [, pa] of pageAudits) {
      if (pa.pageSecurityFindings) {
        for (const raw of pa.pageSecurityFindings) {
          out.push(asFinding(raw, "page_content"));
        }
      }
    }
    return out;
  }, [pageAudits]);

  const totalFindings = siteFindings.length + pageFindings.length;
  const counts = siteReport?.counts ?? { critical: 0, high: 0, medium: 0, low: 0 };

  return (
    <section className="px-6 pb-12">
      <div className="mb-4 flex items-center gap-3">
        <h2 className="text-sm font-semibold text-zinc-200">Security Results</h2>
        {auditStatus === "running" && (
          <span className="inline-flex items-center gap-1.5 text-xs text-indigo-400">
            <span className="h-3 w-3 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
            Running passive checks
          </span>
        )}
        {auditStatus === "complete" && (
          <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-xs font-medium text-emerald-400">
            Complete
          </span>
        )}
      </div>

      <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-6">
        <div className="rounded-lg border border-white/10 bg-zinc-900/60 p-3">
          <p className="text-[10px] uppercase tracking-wider text-zinc-500">Score</p>
          <p className="mt-1 text-xl font-bold text-zinc-100">{siteReport?.overall_score ?? "--"}</p>
        </div>
        <div className="rounded-lg border border-red-500/30 bg-red-500/8 p-3">
          <p className="text-[10px] uppercase tracking-wider text-zinc-500">Critical</p>
          <p className="mt-1 text-xl font-bold text-red-300">{counts.critical}</p>
        </div>
        <div className="rounded-lg border border-orange-500/30 bg-orange-500/8 p-3">
          <p className="text-[10px] uppercase tracking-wider text-zinc-500">High</p>
          <p className="mt-1 text-xl font-bold text-orange-300">{counts.high}</p>
        </div>
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/8 p-3">
          <p className="text-[10px] uppercase tracking-wider text-zinc-500">Medium</p>
          <p className="mt-1 text-xl font-bold text-amber-300">{counts.medium}</p>
        </div>
        <div className="rounded-lg border border-blue-500/30 bg-blue-500/8 p-3">
          <p className="text-[10px] uppercase tracking-wider text-zinc-500">Low</p>
          <p className="mt-1 text-xl font-bold text-blue-300">{counts.low}</p>
        </div>
        <div className="rounded-lg border border-white/10 bg-zinc-900/60 p-3">
          <p className="text-[10px] uppercase tracking-wider text-zinc-500">Findings</p>
          <p className="mt-1 text-xl font-bold text-zinc-100">{totalFindings}</p>
        </div>
      </div>

      {auditStatus === "complete" && totalFindings === 0 && (
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300">
          No findings detected in passive scan.
        </div>
      )}

      <FindingsTable findings={siteFindings} label="Site-wide Findings" />
      <FindingsTable findings={pageFindings} label="Page-specific Findings" />
    </section>
  );
}
