"use client";

import { useMemo, useState } from "react";
import { CheckCircle2, FileText, FileUp, Loader2, MessageSquare, ShieldAlert } from "lucide-react";
import { ConfidenceDot } from "@/components/ConfidenceDot";
import { confirmDocument, getDocument, getDocumentStatus, uploadDocument } from "@/lib/api";

const DEFAULT_FOLLOWUP_QUESTION = "ما أبرز ما ورد في هذا المستند؟";

const stages = ["جاري الرفع…", "قراءة المستند ضوئياً…", "استخلاص البيانات…", "الفهرسة…"];

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

const PRACTICE_AREA_AR: Record<string, string> = {
  corporate_commercial: "شركات وتجاري",
  litigation_dispute: "تقاضي وتسوية نزاعات",
  banking_finance: "مصرفي ومالي",
  real_estate: "عقاري",
  labor_employment: "عمل",
  regulatory_compliance: "تنظيمي وامتثال",
  ip: "ملكية فكرية",
  tax_zakat: "ضريبي وزكوي",
  construction: "تشييد ومقاولات",
  family_inheritance: "أحوال شخصية وميراث",
  criminal: "جزائي",
  administrative: "إداري",
};

type DocDetail = {
  doc_id: string;
  title_ar: string;
  doc_type: string;
  practice_area: string[];
  status: string;
  chunk_count: number;
  extracted_text_preview: string;
  auto_tag_confidence: {
    doc_type?: number;
    practice_area?: number;
    rationale_ar?: string;
  } | null;
};

export function UploadShell() {
  const [file, setFile] = useState<File | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [stageIndex, setStageIndex] = useState(0);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [doc, setDoc] = useState<DocDetail | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [confirmToast, setConfirmToast] = useState("");
  const [followupQuestion, setFollowupQuestion] = useState(DEFAULT_FOLLOWUP_QUESTION);

  const selectedFileLabel = useMemo(() => {
    if (!file) return "لم يتم اختيار ملف";
    return `${file.name} - ${(file.size / 1024 / 1024).toFixed(2)} ميجابايت`;
  }, [file]);

  async function submitUpload() {
    const token = window.localStorage.getItem("suhaiman_access_token");
    if (!token) {
      window.location.href = "/";
      return;
    }
    if (!file) {
      setError("اختر ملفاً قبل بدء الرفع");
      return;
    }
    if (!confirmed) {
      setError("يلزم تأكيد أن المستند لا يحتوي على بيانات عميل حقيقية");
      return;
    }

    setBusy(true);
    setError("");
    setMessage("");
    setDoc(null);
    setConfirmToast("");
    setStageIndex(0);
    const timer = window.setInterval(() => {
      setStageIndex((current) => Math.min(current + 1, stages.length - 1));
    }, 900);

    try {
      const result = await uploadDocument(token, file, confirmed);
      const uploadedDocId = result.doc_id as string;
      await getDocumentStatus(token, uploadedDocId);
      const document = await getDocument(token, uploadedDocId) as DocDetail;
      setStageIndex(stages.length - 1);
      setMessage(result.message_ar ?? "تم الرفع — راجع البيانات المستخلصة قبل الفهرسة.");
      setDoc(document);
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر رفع المستند");
    } finally {
      window.clearInterval(timer);
      setBusy(false);
    }
  }

  async function confirmAndPublish() {
    const token = window.localStorage.getItem("suhaiman_access_token");
    if (!token || !doc) return;
    setConfirming(true);
    setError("");
    try {
      const result = await confirmDocument(token, doc.doc_id, {});
      setConfirmToast(result.message_ar ?? "تم الحفظ والفهرسة — جاهز للبحث");
      setDoc({...doc, status: result.status});
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر تأكيد المستند");
    } finally {
      setConfirming(false);
    }
  }

  return (
    <main className="min-h-screen bg-slate-50">
      <header className="flex h-16 items-center justify-between border-b border-slate-200 bg-white px-8">
        <a href="/home" className="text-xl font-bold text-slate-950">السحيمان</a>
        <div className="text-sm font-medium text-slate-600">رفع مستند جديد</div>
      </header>

      <section className="mx-auto grid max-w-6xl grid-cols-[320px_minmax(0,1fr)] gap-6 px-8 py-8">
        <aside className="space-y-4">
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-amber-900">
            <ShieldAlert className="mb-3 h-5 w-5" aria-hidden="true" />
            <div className="font-semibold">بيئة عرض تجريبي</div>
            <p className="mt-2 text-sm leading-6">لا تُرفع مستندات عملاء حقيقية. OCR والتضمينات والمعالجة الذكية تمر عبر OpenAI ضمن نطاق الاستثناء.</p>
          </div>

          <label className="flex items-start gap-3 rounded-lg border border-slate-200 bg-white p-4 text-sm leading-6 text-slate-800">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(event) => setConfirmed(event.target.checked)}
              className="mt-1 h-4 w-4 accent-teal-700"
            />
            <span>أؤكد أن هذا المستند لا يحتوي على بيانات عميل حقيقية أو بيانات شخصية أو محتوى محمي بسرية الموكل.</span>
          </label>
        </aside>

        <section className="rounded-lg border border-slate-200 bg-white p-8 shadow-sm">
          <h1 className="mb-2 text-2xl font-bold text-slate-950">رفع مستند جديد</h1>
          <p className="mb-6 text-sm text-slate-600">سيظهر تقدم واضح باللغة العربية، وتستهدف المعالجة الاكتمال خلال أقل من دقيقتين.</p>

          <label className="flex min-h-[250px] cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-300 bg-slate-50 text-center hover:border-teal-700">
            <FileUp className="mb-4 h-10 w-10 text-accent-dark" aria-hidden="true" />
            <span className="font-semibold text-slate-900">اسحب الملف وأفلته هنا، أو اختر من جهازك</span>
            <span className="mt-2 text-sm text-slate-500">PDF, DOCX, JPG, PNG — حتى 100 ميجابايت</span>
            <input
              type="file"
              className="sr-only"
              accept=".pdf,.doc,.docx,.jpg,.jpeg,.png,.tif,.tiff"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
          </label>

          <div className="mt-4 rounded-md bg-slate-50 p-3 text-sm text-slate-700">{selectedFileLabel}</div>

          {busy ? (
            <div role="status" className="mt-6 rounded-lg border border-slate-200 p-4">
              <div className="mb-3 flex items-center gap-2 font-semibold text-slate-900">
                <Loader2 className="h-5 w-5 animate-spin text-accent-dark" aria-hidden="true" />
                {stages[stageIndex]}
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-slate-200">
                <div className="h-full rounded-full bg-accent transition-all" style={{width: `${((stageIndex + 1) / stages.length) * 100}%`}} />
              </div>
            </div>
          ) : null}

          {message ? (
            <div role="status" className="mt-6 rounded-lg bg-teal-50 p-4 text-teal-900">
              <div className="flex items-center gap-2 font-semibold">
                <CheckCircle2 className="h-5 w-5" aria-hidden="true" />
                {message}
              </div>
            </div>
          ) : null}

          {/* §8.2.4 Confirmation screen — auto-tagged fields, confidence dots,
              one-click "حفظ ونشر" promotion to published. */}
          {doc && doc.status === "pending_review" ? (
            <section className="mt-6 rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="mb-4 text-xl font-bold text-slate-950">تأكيد بيانات المستند</h2>
              <dl className="space-y-4">
                <div className="grid grid-cols-[140px_1fr] items-start gap-3">
                  <dt className="font-semibold text-slate-700">العنوان</dt>
                  <dd className="text-slate-900">{doc.title_ar}</dd>
                </div>

                <div className="grid grid-cols-[140px_1fr] items-start gap-3">
                  <dt className="font-semibold text-slate-700">نوع المستند</dt>
                  <dd>
                    <div className="text-slate-900">{DOC_TYPE_AR[doc.doc_type] ?? doc.doc_type}</div>
                    <ConfidenceDot value={doc.auto_tag_confidence?.doc_type} />
                  </dd>
                </div>

                <div className="grid grid-cols-[140px_1fr] items-start gap-3">
                  <dt className="font-semibold text-slate-700">مجال الممارسة</dt>
                  <dd>
                    <div className="flex flex-wrap gap-2 text-slate-900">
                      {(doc.practice_area ?? []).length === 0 ? (
                        <span className="text-slate-500">—</span>
                      ) : (
                        (doc.practice_area ?? []).map((pa) => (
                          <span key={pa} className="rounded bg-slate-100 px-2 py-1 text-sm">{PRACTICE_AREA_AR[pa] ?? pa}</span>
                        ))
                      )}
                    </div>
                    <ConfidenceDot value={doc.auto_tag_confidence?.practice_area} />
                  </dd>
                </div>

                <div className="grid grid-cols-[140px_1fr] items-start gap-3">
                  <dt className="font-semibold text-slate-700">عدد المقاطع</dt>
                  <dd className="text-slate-900">{doc.chunk_count}</dd>
                </div>

                {doc.auto_tag_confidence?.rationale_ar ? (
                  <div className="rounded-md bg-slate-50 p-3 text-sm leading-7 text-slate-700">
                    <span className="font-semibold">تعليل النموذج: </span>
                    {doc.auto_tag_confidence.rationale_ar}
                  </div>
                ) : null}
              </dl>

              <div className="mt-5 flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={confirmAndPublish}
                  disabled={confirming}
                  className="rounded-md bg-accent px-5 py-3 font-semibold text-white hover:bg-accent-dark disabled:opacity-60"
                >
                  {confirming ? "جاري التأكيد…" : "حفظ ونشر"}
                </button>
                <a href={`/documents/${doc.doc_id}`} className="rounded-md border border-slate-300 px-5 py-3 font-semibold text-slate-700 hover:bg-slate-50">
                  حفظ كمسودة
                </a>
              </div>
            </section>
          ) : null}

          {/* Post-publish moment of magic: pre-filled question, one click
              takes them to the doc viewer with auto-submitted Q&A. */}
          {confirmToast && doc ? (
            <section role="status" className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 p-5 text-emerald-950">
              <div className="flex items-center gap-2 text-lg font-bold">
                <CheckCircle2 className="h-5 w-5" aria-hidden="true" />
                تم الحفظ والفهرسة ✓
              </div>
              <p className="mt-1 text-sm">المستند الآن قابل للبحث والسؤال.</p>

              <div className="mt-4 rounded-md border border-emerald-200 bg-white p-3">
                <label className="block text-xs font-semibold text-slate-600">جرّب سؤالاً عن المستند:</label>
                <input
                  type="text"
                  value={followupQuestion}
                  onChange={(e) => setFollowupQuestion(e.target.value)}
                  className="mt-1 w-full rounded border border-slate-200 bg-white px-2 py-1.5 font-textArabic text-base leading-7 text-slate-900 outline-none focus:border-teal-600"
                />
              </div>
              <div className="mt-3 flex flex-wrap gap-3">
                <a
                  href={`/documents/${doc.doc_id}?q=${encodeURIComponent(followupQuestion.trim() || DEFAULT_FOLLOWUP_QUESTION)}`}
                  className="inline-flex items-center gap-2 rounded-md bg-accent px-5 py-2.5 font-semibold text-white hover:bg-accent-dark"
                >
                  <MessageSquare className="h-5 w-5" aria-hidden="true" />
                  اسأل عن المستند
                </a>
                <a href={`/documents/${doc.doc_id}`} className="rounded-md border border-emerald-300 px-5 py-2.5 font-semibold text-emerald-900 hover:bg-emerald-100">
                  افتح المستند
                </a>
                <a href="/search" className="rounded-md border border-emerald-300 px-5 py-2.5 font-semibold text-emerald-900 hover:bg-emerald-100">
                  انتقل إلى البحث
                </a>
              </div>
            </section>
          ) : null}

          {doc?.extracted_text_preview ? (
            <section className="mt-6 rounded-lg border border-slate-200 bg-white p-4">
              <div className="mb-3 flex items-center gap-2 font-semibold text-slate-900">
                <FileText className="h-5 w-5 text-accent-dark" aria-hidden="true" />
                معاينة النص المستخرج
              </div>
              <p className="max-h-72 overflow-auto whitespace-pre-wrap font-textArabic text-lg leading-8 text-slate-800">
                {doc.extracted_text_preview}
              </p>
            </section>
          ) : null}

          {error ? <div role="alert" className="mt-6 rounded-lg bg-red-50 p-4 text-red-700">{error}</div> : null}

          <div className="mt-6 flex gap-3">
            <button
              type="button"
              onClick={submitUpload}
              disabled={busy}
              className="rounded-md bg-accent px-5 py-3 font-semibold text-white hover:bg-accent-dark disabled:cursor-not-allowed disabled:opacity-60"
            >
              رفع المستند
            </button>
            <a href="/home" className="rounded-md border border-slate-300 px-5 py-3 font-semibold text-slate-700 hover:bg-slate-50">
              إلغاء
            </a>
          </div>
        </section>
      </section>
    </main>
  );
}
