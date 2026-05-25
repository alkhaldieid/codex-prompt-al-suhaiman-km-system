"use client";

import { useEffect, useMemo, useState } from "react";
import { ChevronDown, ExternalLink, FileText, Loader2, Search } from "lucide-react";
import { searchRegulations } from "@/lib/api";

const PRACTICE_AREA_AR: Record<string, string> = {
  corporate_commercial: "شركات وتجاري",
  litigation_dispute: "تقاضي وتسوية",
  banking_finance: "مصرفي ومالي",
  real_estate: "عقاري",
  labor_employment: "عمل",
  regulatory_compliance: "تنظيمي وامتثال",
  ip: "ملكية فكرية",
  tax_zakat: "ضريبي وزكوي",
  construction: "تشييد",
  family_inheritance: "أحوال شخصية",
  criminal: "جزائي",
  administrative: "إداري",
};

const DOC_TYPE_AR: Record<string, string> = {
  judicial_ruling: "حكم قضائي",
  legal_opinion: "رأي قانوني",
  memo: "مذكرة",
  pleading: "لائحة",
  contract: "عقد",
  engagement_letter: "خطاب ارتباط",
  regulation: "لائحة تنظيمية",
  royal_decree: "مرسوم ملكي",
  council_resolution: "قرار مجلس الوزراء",
  circular: "تعميم",
  template: "نموذج",
  precedent_note: "مذكرة سابقة",
  other: "أخرى",
};

const SOURCE_BADGE: Record<string, string> = {
  track1_external: "تنظيمي",
  track2_legacy: "قديم",
  track3_capture: "مكتبة",
  synthetic: "تجريبي",
};

type Result = {
  doc_id: string;
  chunk_id: string;
  title_ar: string;
  snippet_ar: string;
  doc_type: string;
  practice_area: string[];
  paragraph_no: number | null;
  score: number;
  bm25_score: number;
  vector_score: number;
  source_track: string;
  source_url: string | null;
};

type Grouped = {
  doc_id: string;
  title_ar: string;
  doc_type: string;
  practice_area: string[];
  source_track: string;
  source_url: string | null;
  best: Result;           // best-scoring chunk
  others: Result[];       // remaining chunks for the same doc, sorted by score
};

export function SearchShell() {
  const [q, setQ] = useState("");
  const [submitted, setSubmitted] = useState("");
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState<Result[]>([]);
  const [error, setError] = useState("");
  const [tookMs, setTookMs] = useState<number | null>(null);
  const [filterPractice, setFilterPractice] = useState<string | null>(null);
  const [filterDocType, setFilterDocType] = useState<string | null>(null);
  const [filterTrack, setFilterTrack] = useState<string | null>(null);
  const [expandedDocId, setExpandedDocId] = useState<string | null>(null);
  const [showScoresForId, setShowScoresForId] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const initial = params.get("q") ?? "";
    if (initial) {
      setQ(initial);
      void runSearch(initial);
    }
  }, []);

  async function runSearch(query: string) {
    const token = window.localStorage.getItem("suhaiman_access_token");
    if (!token) {
      window.location.href = "/";
      return;
    }
    setBusy(true);
    setError("");
    setSubmitted(query);
    setExpandedDocId(null);
    setShowScoresForId(null);
    try {
      const data = await searchRegulations(token, query);
      setResults((data.results ?? []) as Result[]);
      setTookMs(data.took_ms ?? null);
      const params = new URLSearchParams(window.location.search);
      params.set("q", query);
      window.history.replaceState(null, "", `${window.location.pathname}?${params.toString()}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر البحث");
    } finally {
      setBusy(false);
    }
  }

  const filtered = results.filter((r) => {
    if (filterPractice && !(r.practice_area ?? []).includes(filterPractice)) return false;
    if (filterDocType && r.doc_type !== filterDocType) return false;
    if (filterTrack && r.source_track !== filterTrack) return false;
    return true;
  });

  // Group by doc_id, sorting within each doc by score desc.
  const grouped: Grouped[] = useMemo(() => {
    const byDoc = new Map<string, Result[]>();
    for (const r of filtered) {
      const arr = byDoc.get(r.doc_id) ?? [];
      arr.push(r);
      byDoc.set(r.doc_id, arr);
    }
    const out: Grouped[] = [];
    for (const [doc_id, rs] of byDoc) {
      rs.sort((a, b) => b.score - a.score);
      const [best, ...others] = rs;
      out.push({
        doc_id,
        title_ar: best.title_ar,
        doc_type: best.doc_type,
        practice_area: best.practice_area,
        source_track: best.source_track,
        source_url: best.source_url,
        best,
        others,
      });
    }
    out.sort((a, b) => b.best.score - a.best.score);
    return out;
  }, [filtered]);

  const availablePractice = Array.from(new Set(results.flatMap((r) => r.practice_area ?? [])));
  const availableDocType = Array.from(new Set(results.map((r) => r.doc_type)));
  const availableTrack = Array.from(new Set(results.map((r) => r.source_track)));

  return (
    <main className="min-h-screen bg-slate-50">
      <header className="flex h-16 items-center justify-between border-b border-slate-200 bg-white px-8">
        <a href="/home" className="text-xl font-bold text-slate-950">السحيمان</a>
        <div className="text-sm font-medium text-slate-600">البحث في الأنظمة والسوابق</div>
      </header>

      <section className="mx-auto max-w-6xl px-8 py-8">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (q.trim()) void runSearch(q.trim());
          }}
          className="mb-6 flex gap-3"
        >
          <input
            type="text"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="اكتب سؤالك أو ابحث عن نظام"
            className="flex-1 rounded-md border border-slate-300 bg-white px-4 py-3 font-textArabic text-lg leading-7 text-slate-900 outline-none focus:border-teal-600"
          />
          <button
            type="submit"
            disabled={busy || !q.trim()}
            className="flex items-center gap-2 rounded-md bg-accent px-5 py-3 font-semibold text-white hover:bg-accent-dark disabled:opacity-60"
          >
            {busy ? <Loader2 className="h-5 w-5 animate-spin" /> : <Search className="h-5 w-5" />}
            بحث
          </button>
        </form>

        {error ? <div role="alert" className="mb-4 rounded-lg bg-red-50 p-4 text-red-700">{error}</div> : null}

        {submitted && !busy ? (
          <div className="mb-4 text-sm text-slate-600">
            {grouped.length} مستند · {filtered.length} مقطع مطابق لـ{" "}
            <span className="font-semibold text-slate-800">{submitted}</span>
            {tookMs !== null ? <> · زمن البحث {tookMs}ms</> : null}
          </div>
        ) : null}

        <div className="grid grid-cols-[1fr_280px] gap-6">
          {/* Main results column — grouped per document */}
          <section>
            {grouped.length === 0 && submitted && !busy ? (
              <div className="rounded-lg border border-slate-200 bg-white p-6 text-center text-slate-600">
                لا توجد نتائج مطابقة. جرّب صياغة أخرى أو أزل الفلاتر.
              </div>
            ) : null}
            <ul className="space-y-3">
              {grouped.map((g) => {
                const isExpanded = expandedDocId === g.doc_id;
                const isShowingScores = showScoresForId === g.doc_id;
                return (
                  <li key={g.doc_id} className="rounded-lg border border-slate-200 bg-white p-5 transition hover:border-teal-600">
                    <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                      <span className="rounded bg-teal-50 px-2 py-0.5 font-semibold text-teal-800">
                        {SOURCE_BADGE[g.source_track] ?? g.source_track}
                      </span>
                      <span className="rounded bg-slate-100 px-2 py-0.5">{DOC_TYPE_AR[g.doc_type] ?? g.doc_type}</span>
                      {(g.practice_area ?? []).map((pa) => (
                        <span key={pa} className="rounded bg-slate-100 px-2 py-0.5">{PRACTICE_AREA_AR[pa] ?? pa}</span>
                      ))}
                      <span className="ms-auto text-slate-400">¶{g.best.paragraph_no ?? "?"}</span>
                    </div>

                    <a
                      href={`/documents/${g.doc_id}?chunk=${g.best.chunk_id}`}
                      className="block text-lg font-bold text-slate-950 hover:text-accent-dark"
                    >
                      <FileText className="me-2 inline h-5 w-5 align-middle text-slate-400" aria-hidden="true" />
                      {g.title_ar}
                    </a>

                    <p
                      className="mt-2 font-textArabic text-base leading-8 text-slate-700"
                      dangerouslySetInnerHTML={{__html: g.best.snippet_ar.replace(/<em>/g, '<em class="bg-amber-100 not-italic font-semibold">')}}
                    />

                    <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-slate-500">
                      {g.others.length > 0 ? (
                        <button
                          type="button"
                          onClick={() => setExpandedDocId(isExpanded ? null : g.doc_id)}
                          className="inline-flex items-center gap-1 font-semibold text-slate-700 hover:text-accent-dark"
                        >
                          <ChevronDown className={`h-4 w-4 transition ${isExpanded ? "rotate-180" : ""}`} aria-hidden="true" />
                          {g.others.length + 1} مقطع مطابق
                        </button>
                      ) : (
                        <span>مقطع واحد مطابق</span>
                      )}

                      <button
                        type="button"
                        onClick={() => setShowScoresForId(isShowingScores ? null : g.doc_id)}
                        className="inline-flex items-center gap-1 text-slate-500 hover:text-slate-700"
                      >
                        <ChevronDown className={`h-3.5 w-3.5 transition ${isShowingScores ? "rotate-180" : ""}`} aria-hidden="true" />
                        تفاصيل الترتيب
                      </button>

                      {g.source_url ? (
                        <a href={g.source_url} target="_blank" rel="noopener noreferrer" className="ms-auto flex items-center gap-1 hover:text-teal-700">
                          المصدر <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                        </a>
                      ) : null}
                    </div>

                    {isShowingScores ? (
                      <div className="mt-3 grid grid-cols-3 gap-2 rounded-md bg-slate-50 p-3 text-xs text-slate-600">
                        <div>BM25: <span className="font-mono">{g.best.bm25_score.toFixed(2)}</span></div>
                        <div>Vector: <span className="font-mono">{g.best.vector_score.toFixed(3)}</span></div>
                        <div>Fused: <span className="font-mono">{g.best.score.toFixed(4)}</span></div>
                      </div>
                    ) : null}

                    {isExpanded && g.others.length > 0 ? (
                      <ul className="mt-4 space-y-2 border-t border-slate-200 pt-4">
                        {g.others.map((o) => (
                          <li key={o.chunk_id} className="rounded bg-slate-50 p-3">
                            <div className="mb-1 text-xs text-slate-500">¶{o.paragraph_no ?? "?"}</div>
                            <p
                              className="font-textArabic text-sm leading-7 text-slate-700"
                              dangerouslySetInnerHTML={{__html: o.snippet_ar.replace(/<em>/g, '<em class="bg-amber-100 not-italic font-semibold">')}}
                            />
                            <a
                              href={`/documents/${g.doc_id}?chunk=${o.chunk_id}`}
                              className="mt-1 inline-block text-xs font-semibold text-accent-dark hover:underline"
                            >
                              افتح هذا المقطع ←
                            </a>
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          </section>

          {/* Filters rail */}
          <aside className="space-y-4">
            <FilterCard title="نوع المستند" items={availableDocType} labels={DOC_TYPE_AR} value={filterDocType} onChange={setFilterDocType} />
            <FilterCard title="مجال الممارسة" items={availablePractice} labels={PRACTICE_AREA_AR} value={filterPractice} onChange={setFilterPractice} />
            <FilterCard title="المصدر" items={availableTrack} labels={SOURCE_BADGE} value={filterTrack} onChange={setFilterTrack} />
          </aside>
        </div>
      </section>
    </main>
  );
}

function FilterCard({
  title,
  items,
  labels,
  value,
  onChange,
}: {
  title: string;
  items: string[];
  labels: Record<string, string>;
  value: string | null;
  onChange: (v: string | null) => void;
}) {
  if (items.length === 0) return null;
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="mb-3 text-sm font-semibold text-slate-800">{title}</div>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => onChange(null)}
          className={`rounded-full px-3 py-1 text-xs ${value === null ? "bg-accent text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"}`}
        >
          الكل
        </button>
        {items.map((item) => (
          <button
            key={item}
            type="button"
            onClick={() => onChange(item)}
            className={`rounded-full px-3 py-1 text-xs ${value === item ? "bg-accent text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"}`}
          >
            {labels[item] ?? item}
          </button>
        ))}
      </div>
    </div>
  );
}
