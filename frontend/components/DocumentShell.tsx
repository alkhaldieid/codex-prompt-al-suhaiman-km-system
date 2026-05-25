"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Loader2, MessageSquare, FileText, ExternalLink } from "lucide-react";
import { askDocument, getDocument } from "@/lib/api";
import { Citation, renderAnswerWithCitationChips } from "@/lib/citations";

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

type DocDetail = {
  doc_id: string;
  title_ar: string;
  doc_type: string;
  practice_area: string[];
  status: string;
  chunk_count: number;
  extracted_text_preview: string;
  source_url: string | null;
};

type AskTurn = {
  question: string;
  answer: string;
  citations: Citation[];
  took_ms: number | null;
  model: string | null;
  refused: boolean;
};

type Props = {
  docId: string;
};

export function DocumentShell({docId}: Props) {
  const [doc, setDoc] = useState<DocDetail | null>(null);
  const [error, setError] = useState("");
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [turns, setTurns] = useState<AskTurn[]>([]);
  const [highlightParagraph, setHighlightParagraph] = useState<number | null>(null);

  const readingPaneRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const token = window.localStorage.getItem("suhaiman_access_token");
    if (!token) {
      window.location.href = "/";
      return;
    }
    getDocument(token, docId)
      .then((d) => setDoc(d as DocDetail))
      .catch((err) => setError(err instanceof Error ? err.message : "تعذر تحميل المستند"));
  }, [docId]);

  // Split the document into "paragraphs" so we can put a paragraph
  // number in the margin and jump-scroll on citation click. Paragraphs
  // are double-newline-separated — same split rule the backend uses.
  const paragraphs = useMemo(() => {
    if (!doc?.extracted_text_preview) return [];
    return doc.extracted_text_preview
      .split(/\n{2,}/)
      .map((p) => p.trim())
      .filter(Boolean);
  }, [doc?.extracted_text_preview]);

  function scrollToParagraph(n: number) {
    setHighlightParagraph(n);
    const el = readingPaneRef.current?.querySelector(`[data-paragraph="${n}"]`);
    if (el instanceof HTMLElement) {
      el.scrollIntoView({behavior: "smooth", block: "center"});
    }
    window.setTimeout(() => setHighlightParagraph(null), 2200);
  }

  async function submitQuestion() {
    await submitQuestionImmediate(question);
  }

  // Auto-submit any ?q= passed in the URL (e.g. from the UploadShell
  // success block). Runs once when the doc loads.
  useEffect(() => {
    if (!doc) return;
    const params = new URLSearchParams(window.location.search);
    const initialQ = params.get("q");
    if (initialQ && !asking && turns.length === 0) {
      setQuestion(initialQ);
      void submitQuestionImmediate(initialQ);
      // Remove the param so a manual reload doesn't re-fire.
      params.delete("q");
      const qs = params.toString();
      window.history.replaceState(null, "", window.location.pathname + (qs ? "?" + qs : ""));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [doc]);

  async function submitQuestionImmediate(q: string) {
    const token = window.localStorage.getItem("suhaiman_access_token");
    if (!token || !q.trim()) return;
    setAsking(true);
    try {
      const data = await askDocument(token, docId, q.trim());
      setTurns((prev) => [
        ...prev,
        {
          question: q.trim(),
          answer: data.answer_ar ?? "",
          citations: data.citations ?? [],
          took_ms: data.took_ms ?? null,
          model: data.model ?? null,
          refused: Boolean(data.refused),
        },
      ]);
      setQuestion("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر توليد الإجابة");
    } finally {
      setAsking(false);
    }
  }

  if (error) {
    return (
      <main className="min-h-screen bg-slate-50 p-8">
        <div className="rounded-lg bg-red-50 p-4 text-red-700">{error}</div>
      </main>
    );
  }
  if (!doc) {
    return (
      <main className="min-h-screen bg-slate-50 p-8">
        <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-50">
      <header className="flex h-16 items-center justify-between border-b border-slate-200 bg-white px-8">
        <a href="/home" className="text-xl font-bold text-slate-950">السحيمان</a>
        <div className="flex items-center gap-3 text-sm font-medium text-slate-600">
          <span className="rounded bg-slate-100 px-2 py-0.5">{DOC_TYPE_AR[doc.doc_type] ?? doc.doc_type}</span>
          <span>الحالة: {doc.status}</span>
        </div>
      </header>

      <section className="mx-auto grid max-w-7xl grid-cols-[minmax(0,2fr)_minmax(0,1fr)] gap-6 px-8 py-8">
        {/* Reading pane — visually-right in RTL */}
        <article ref={readingPaneRef} className="rounded-lg border border-slate-200 bg-white p-8 shadow-sm">
          <h1 className="mb-2 font-textArabic text-2xl font-bold text-slate-950">{doc.title_ar}</h1>
          <div className="mb-6 flex flex-wrap gap-2 text-xs text-slate-500">
            <span className="rounded bg-slate-100 px-2 py-0.5">{DOC_TYPE_AR[doc.doc_type] ?? doc.doc_type}</span>
            {(doc.practice_area ?? []).map((pa) => (
              <span key={pa} className="rounded bg-slate-100 px-2 py-0.5">{pa}</span>
            ))}
            <span>{doc.chunk_count} مقطعاً</span>
            {doc.source_url ? (
              <a href={doc.source_url} target="_blank" rel="noopener noreferrer" className="ms-auto flex items-center gap-1 text-teal-700 hover:underline">
                المصدر الرسمي <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
              </a>
            ) : null}
          </div>

          <div className="space-y-4 font-textArabic text-lg leading-9 text-slate-900">
            {paragraphs.map((p, idx) => {
              const n = idx + 1;
              const isHighlighted = highlightParagraph === n;
              return (
                <div
                  key={n}
                  data-paragraph={n}
                  className={`grid grid-cols-[40px_1fr] gap-3 rounded p-2 transition ${isHighlighted ? "bg-amber-50 ring-2 ring-amber-300" : ""}`}
                >
                  <span className="select-none pt-1 text-left font-mono text-xs text-slate-400" aria-hidden="true">
                    ¶{n}
                  </span>
                  <p className="whitespace-pre-wrap">{p}</p>
                </div>
              );
            })}
            {paragraphs.length === 0 ? (
              <div className="text-slate-500">لا يوجد نص قابل للعرض. قد يكون المستند بحاجة إلى OCR.</div>
            ) : null}
          </div>
        </article>

        {/* Tools pane: Q&A panel + metadata — visually-left in RTL */}
        <aside className="space-y-4">
          <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-3 flex items-center gap-2 text-base font-semibold text-slate-900">
              <MessageSquare className="h-5 w-5 text-accent-dark" aria-hidden="true" />
              اسأل عن هذا المستند
            </div>
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              rows={3}
              placeholder="اكتب سؤالك بالعربية…"
              className="w-full rounded-md border border-slate-300 p-3 font-textArabic text-base leading-7 text-slate-900 outline-none focus:border-teal-600"
            />
            <button
              type="button"
              onClick={submitQuestion}
              disabled={asking || !question.trim()}
              className="mt-3 flex w-full items-center justify-center gap-2 rounded-md bg-accent px-4 py-2.5 font-semibold text-white hover:bg-accent-dark disabled:opacity-60"
            >
              {asking ? <Loader2 className="h-5 w-5 animate-spin" /> : <MessageSquare className="h-5 w-5" />}
              اسأل
            </button>

            <div className="mt-5 space-y-4">
              {turns.length === 0 ? (
                <p className="text-sm text-slate-500">اطرح سؤالك وستظهر الإجابة هنا مع مراجع للفقرات.</p>
              ) : null}
              {turns.map((t, i) => (
                <div key={i} className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm">
                  <div className="mb-2 font-semibold text-slate-900">{t.question}</div>
                  <div className="font-textArabic text-base leading-8 text-slate-800">
                    {t.refused ? (
                      <span className="text-amber-800">{t.answer}</span>
                    ) : (
                      renderAnswerWithCitationChips(
                        t.answer,
                        t.citations,
                        (n) => scrollToParagraph(n),
                      )
                    )}
                  </div>
                  {t.citations.length > 0 ? (
                    <ul className="mt-3 space-y-1 text-xs text-slate-600">
                      {t.citations.map((c) => (
                        <li key={c.chunk_id} className="flex items-start gap-2">
                          <button
                            type="button"
                            onClick={() => c.paragraph_no && scrollToParagraph(c.paragraph_no)}
                            className="rounded bg-teal-100 px-1.5 py-0.5 font-semibold text-teal-900 hover:bg-teal-200"
                          >
                            {c.marker}
                          </button>
                          <span className="line-clamp-2">{c.quoted_text_ar}</span>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                  <div className="mt-2 flex items-center gap-2 text-xs text-slate-400">
                    {t.model ? <span dir="ltr">{t.model}</span> : null}
                    {t.took_ms !== null ? <span dir="ltr">· {t.took_ms}ms</span> : null}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-900">
              <FileText className="h-4 w-4 text-slate-500" aria-hidden="true" />
              بيانات المستند
            </div>
            <dl className="space-y-1.5 text-sm text-slate-700">
              <div className="flex justify-between"><dt>النوع</dt><dd className="font-medium text-slate-900">{DOC_TYPE_AR[doc.doc_type] ?? doc.doc_type}</dd></div>
              <div className="flex justify-between"><dt>المقاطع</dt><dd className="font-mono">{doc.chunk_count}</dd></div>
              <div className="flex justify-between"><dt>الحالة</dt><dd>{doc.status}</dd></div>
            </dl>
          </div>
        </aside>
      </section>
    </main>
  );
}
