"use client";

import { useEffect, useState } from "react";
import { Loader2, Search, FileText, ExternalLink } from "lucide-react";
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

  useEffect(() => {
    // Read q from query string on mount
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
    try {
      const data = await searchRegulations(token, query);
      setResults((data.results ?? []) as Result[]);
      setTookMs(data.took_ms ?? null);
      // Update URL without nav
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

  // Compute available filter chips from current results
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
            placeholder="ابحث في السوابق والآراء والأنظمة…"
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
            {filtered.length} نتيجة لـ <span className="font-semibold text-slate-800">{submitted}</span>
            {tookMs !== null ? <> · زمن البحث {tookMs}ms</> : null}
          </div>
        ) : null}

        <div className="grid grid-cols-[1fr_280px] gap-6">
          {/* Main results column */}
          <section>
            {filtered.length === 0 && submitted && !busy ? (
              <div className="rounded-lg border border-slate-200 bg-white p-6 text-center text-slate-600">
                لا توجد نتائج مطابقة. جرّب صياغة أخرى أو أزل الفلاتر.
              </div>
            ) : null}
            <ul className="space-y-3">
              {filtered.map((r) => (
                <li key={r.chunk_id} className="rounded-lg border border-slate-200 bg-white p-5 transition hover:border-teal-600">
                  <div className="mb-2 flex items-center gap-2 text-xs text-slate-500">
                    <span className="rounded bg-teal-50 px-2 py-0.5 font-semibold text-teal-800">
                      {SOURCE_BADGE[r.source_track] ?? r.source_track}
                    </span>
                    <span className="rounded bg-slate-100 px-2 py-0.5">{DOC_TYPE_AR[r.doc_type] ?? r.doc_type}</span>
                    {(r.practice_area ?? []).map((pa) => (
                      <span key={pa} className="rounded bg-slate-100 px-2 py-0.5">{PRACTICE_AREA_AR[pa] ?? pa}</span>
                    ))}
                    <span className="ms-auto text-slate-400">¶{r.paragraph_no ?? "?"}</span>
                  </div>
                  <a href={`/documents/${r.doc_id}?chunk=${r.chunk_id}`} className="block text-lg font-bold text-slate-950 hover:text-accent-dark">
                    <FileText className="me-2 inline h-5 w-5 align-middle text-slate-400" aria-hidden="true" />
                    {r.title_ar}
                  </a>
                  <p
                    className="mt-2 font-textArabic text-base leading-8 text-slate-700"
                    dangerouslySetInnerHTML={{__html: r.snippet_ar.replace(/<em>/g, '<em class="bg-amber-100 not-italic font-semibold">')}}
                  />
                  <div className="mt-3 flex items-center gap-4 text-xs text-slate-500">
                    <span>BM25: <span className="font-mono">{r.bm25_score.toFixed(2)}</span></span>
                    <span>Vector: <span className="font-mono">{r.vector_score.toFixed(3)}</span></span>
                    <span>Fused: <span className="font-mono">{r.score.toFixed(4)}</span></span>
                    {r.source_url ? (
                      <a href={r.source_url} target="_blank" rel="noopener noreferrer" className="ms-auto flex items-center gap-1 hover:text-teal-700">
                        المصدر <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                      </a>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          </section>

          {/* Filters rail (visually-left in RTL flow) */}
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
