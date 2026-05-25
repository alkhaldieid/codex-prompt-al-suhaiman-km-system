"use client";

import { useEffect, useRef, useState } from "react";
import { Loader2, MessageSquare, FileText, Search as SearchIcon, Upload } from "lucide-react";
import { askRegulations, getMe } from "@/lib/api";
import { Citation, renderAnswerWithCitationChips } from "@/lib/citations";

type User = {
  display_name_ar: string;
  email: string;
  role: string;
};

type AskResponse = {
  answer_ar: string;
  citations: Citation[];
  model: string | null;
  took_ms: number | null;
  retrieved_chunks: number;
  refused: boolean;
  refusal_reason: string | null;
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

const EXAMPLE_QUESTIONS = [
  "ما اختصاصات المحاكم التجارية؟",
  "ما إجراءات التنفيذ على المدين؟",
  "ما الواجبات المهنية للمحامي؟",
];

export function HomeShell() {
  const [user, setUser] = useState<User | null>(null);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [response, setResponse] = useState<AskResponse | null>(null);
  const [error, setError] = useState("");

  // Used to scroll a cited card into view + flash it when its chip is clicked.
  const [highlightedDocId, setHighlightedDocId] = useState<string | null>(null);
  const citedCardsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const token = window.localStorage.getItem("suhaiman_access_token");
    if (!token) {
      window.location.href = "/";
      return;
    }
    getMe(token)
      .then(setUser)
      .catch(() => {
        window.localStorage.removeItem("suhaiman_access_token");
        window.location.href = "/";
      });
  }, []);

  async function submitQuestion(text?: string) {
    const q = (text ?? question).trim();
    if (!q) return;
    const token = window.localStorage.getItem("suhaiman_access_token");
    if (!token) {
      window.location.href = "/";
      return;
    }
    setBusy(true);
    setError("");
    setResponse(null);
    if (text) setQuestion(text);
    try {
      const data = (await askRegulations(token, q)) as AskResponse;
      setResponse(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر توليد الإجابة");
    } finally {
      setBusy(false);
    }
  }

  function onCitationChipClick(_n: number, cited: Citation | undefined) {
    if (!cited) return;
    setHighlightedDocId(cited.doc_id);
    const el = citedCardsRef.current?.querySelector(`[data-doc-id="${cited.doc_id}"]`);
    if (el instanceof HTMLElement) {
      el.scrollIntoView({behavior: "smooth", block: "center"});
    }
    window.setTimeout(() => setHighlightedDocId(null), 2200);
  }

  return (
    <main className="min-h-screen bg-slate-50">
      <header className="flex h-16 items-center justify-between border-b border-slate-200 bg-white px-8">
        <a href="/home" className="text-xl font-bold text-slate-950">السحيمان</a>
        <div className="text-sm">
          <div className="font-semibold text-slate-900">{user?.display_name_ar ?? "..."}</div>
          <div dir="ltr" className="text-slate-500">{user?.email ?? ""}</div>
        </div>
      </header>

      <section className="mx-auto max-w-4xl px-6 py-12">
        {/* HERO */}
        <div className="text-center">
          <h1 className="text-3xl font-bold text-slate-950">اسأل عن الأنظمة السعودية</h1>
          <p className="mx-auto mt-3 max-w-2xl text-lg text-slate-600">
            ٢٥ نظاماً ولائحة سعودية مفهرسة في القضاء، التوثيق، التنفيذ، العقار، والمحاماة.
          </p>
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            void submitQuestion();
          }}
          className="mt-8"
        >
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            rows={3}
            placeholder="اكتب سؤالك بالعربية..."
            className="w-full rounded-lg border border-slate-300 bg-white p-4 font-textArabic text-lg leading-8 text-slate-900 outline-none focus:border-teal-600"
          />

          <div className="mt-4 flex flex-wrap items-center gap-2">
            {EXAMPLE_QUESTIONS.map((ex) => (
              <button
                key={ex}
                type="button"
                onClick={() => void submitQuestion(ex)}
                disabled={busy}
                className="rounded-full border border-slate-300 bg-white px-4 py-1.5 text-sm text-slate-700 hover:border-teal-600 hover:bg-teal-50 disabled:opacity-60"
              >
                {ex}
              </button>
            ))}
            <button
              type="submit"
              disabled={busy || !question.trim()}
              className="ms-auto flex items-center gap-2 rounded-md bg-accent px-6 py-2.5 font-semibold text-white hover:bg-accent-dark disabled:opacity-60"
            >
              {busy ? <Loader2 className="h-5 w-5 animate-spin" /> : <MessageSquare className="h-5 w-5" />}
              اسأل
            </button>
          </div>
        </form>

        {/* ANSWER BLOCK */}
        {busy ? (
          <div role="status" className="mt-8 flex items-center justify-center gap-3 rounded-lg border border-slate-200 bg-white p-6 text-slate-700">
            <Loader2 className="h-5 w-5 animate-spin text-accent-dark" aria-hidden="true" />
            جارٍ البحث في الأنظمة...
          </div>
        ) : null}

        {error ? (
          <div role="alert" className="mt-8 rounded-lg bg-red-50 p-4 text-red-700">
            {error}
          </div>
        ) : null}

        {response && !busy ? (
          <section className="mt-8">
            {response.refused ? (
              <div role="status" className="rounded-lg bg-amber-50 p-5 text-amber-900">
                <div className="font-semibold">لم يتمكن النموذج من الإجابة بثقة كافية.</div>
                <p className="mt-2 text-sm leading-7">{response.answer_ar}</p>
                <p className="mt-3 text-sm">جرّب صياغة أوضح، أو سمِّ النظام الذي تسأل عنه (مثلاً: "وفق نظام الإثبات...").</p>
              </div>
            ) : (
              <>
                <div className="mb-2 text-xs text-slate-500">
                  أُجيب خلال {response.took_ms ?? 0}ms
                  {response.model ? <> · <span dir="ltr">{response.model}</span></> : null}
                </div>

                <article className="rounded-lg border border-teal-100 bg-teal-50/50 p-6 font-textArabic text-base leading-9 text-slate-900">
                  {renderAnswerWithCitationChips(response.answer_ar, response.citations, onCitationChipClick)}
                </article>

                {response.citations.length > 0 ? (
                  <div ref={citedCardsRef} className="mt-6 space-y-3">
                    <h2 className="text-sm font-semibold text-slate-700">المراجع المستشهد بها</h2>
                    {dedupCitationsByDoc(response.citations).map((c) => (
                      <article
                        key={c.doc_id}
                        data-doc-id={c.doc_id}
                        className={`rounded-lg border bg-white p-4 transition ${highlightedDocId === c.doc_id ? "border-amber-400 bg-amber-50" : "border-slate-200"}`}
                      >
                        <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
                          <span className="rounded bg-teal-100 px-2 py-0.5 font-mono font-semibold text-teal-900">{c.marker}</span>
                          {c.doc_type ? <span className="rounded bg-slate-100 px-2 py-0.5 text-slate-700">{DOC_TYPE_AR[c.doc_type] ?? c.doc_type}</span> : null}
                        </div>
                        <h3 className="text-base font-bold text-slate-950">{c.title_ar ?? "—"}</h3>
                        <p className="mt-2 font-textArabic text-sm leading-7 text-slate-700">
                          {(c.quoted_text_ar ?? "").slice(0, 400)}
                          {(c.quoted_text_ar ?? "").length > 400 ? "…" : ""}
                        </p>
                        <a
                          href={`/documents/${c.doc_id}?chunk=${c.chunk_id}`}
                          className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-accent-dark hover:underline"
                        >
                          اقرأ المستند ←
                        </a>
                      </article>
                    ))}
                  </div>
                ) : null}
              </>
            )}
          </section>
        ) : null}

        {/* SECONDARY: shows only after a first response */}
        {response ? (
          <section className="mt-12 grid gap-4 sm:grid-cols-2">
            <a
              href="/search"
              className="group flex items-center gap-4 rounded-lg border border-slate-200 bg-white p-5 transition hover:border-teal-600 hover:shadow"
            >
              <SearchIcon className="h-6 w-6 text-accent-dark" aria-hidden="true" />
              <div>
                <div className="font-semibold text-slate-950">بحث متقدم</div>
                <div className="text-sm text-slate-600">ابحث في النصوص مع فلاتر بحسب النظام والمصدر.</div>
              </div>
            </a>
            <a
              href="/upload"
              className="group flex items-center gap-4 rounded-lg border border-slate-200 bg-white p-5 transition hover:border-teal-600 hover:shadow"
            >
              <Upload className="h-6 w-6 text-accent-dark" aria-hidden="true" />
              <div>
                <div className="font-semibold text-slate-950">إضافة مستند</div>
                <div className="text-sm text-slate-600">ارفع حكمًا أو رأيًا قانونيًا لإضافته إلى المكتبة.</div>
              </div>
            </a>
          </section>
        ) : null}
      </section>
    </main>
  );
}

// Keep one card per cited document — the chip already shows ¶N specificity,
// repeating the title for every chunk of the same doc just adds noise.
function dedupCitationsByDoc(citations: Citation[]): Citation[] {
  const seen = new Set<string>();
  const out: Citation[] = [];
  for (const c of citations) {
    if (seen.has(c.doc_id)) continue;
    seen.add(c.doc_id);
    out.push(c);
  }
  return out;
}
