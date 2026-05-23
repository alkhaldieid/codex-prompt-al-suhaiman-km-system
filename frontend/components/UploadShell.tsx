"use client";

import { useMemo, useState } from "react";
import { CheckCircle2, FileText, FileUp, Loader2, ShieldAlert } from "lucide-react";
import { getDocument, getDocumentStatus, uploadDocument } from "@/lib/api";

const stages = ["جاري الرفع…", "قراءة المستند ضوئياً…", "استخلاص البيانات…", "الفهرسة…"];

export function UploadShell() {
  const [file, setFile] = useState<File | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [stageIndex, setStageIndex] = useState(0);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [docId, setDocId] = useState("");
  const [statusLabel, setStatusLabel] = useState("");
  const [preview, setPreview] = useState("");
  const [chunkCount, setChunkCount] = useState<number | null>(null);

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
    setDocId("");
    setStatusLabel("");
    setPreview("");
    setChunkCount(null);
    setStageIndex(0);
    const timer = window.setInterval(() => {
      setStageIndex((current) => Math.min(current + 1, stages.length - 1));
    }, 900);

    try {
      const result = await uploadDocument(token, file, confirmed);
      const uploadedDocId = result.doc_id as string;
      const status = await getDocumentStatus(token, uploadedDocId);
      const document = await getDocument(token, uploadedDocId);
      setStageIndex(stages.length - 1);
      setMessage(result.message_ar ?? "تم الرفع — ستستكمل المعالجة خلال أقل من دقيقتين");
      setDocId(uploadedDocId);
      setStatusLabel(status.stage_label_ar ?? "");
      setPreview(document.extracted_text_preview ?? "");
      setChunkCount(document.chunk_count ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر رفع المستند");
    } finally {
      window.clearInterval(timer);
      setBusy(false);
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
              {docId ? (
                <div className="mt-3 space-y-1 text-sm">
                  <div dir="ltr" className="text-left">doc_id: {docId}</div>
                  <div>الحالة: {statusLabel}</div>
                  <div>عدد المقاطع: {chunkCount ?? 0}</div>
                </div>
              ) : null}
            </div>
          ) : null}

          {preview ? (
            <section className="mt-6 rounded-lg border border-slate-200 bg-white p-4">
              <div className="mb-3 flex items-center gap-2 font-semibold text-slate-900">
                <FileText className="h-5 w-5 text-accent-dark" aria-hidden="true" />
                معاينة النص المستخرج
              </div>
              <p className="max-h-72 overflow-auto whitespace-pre-wrap font-textArabic text-lg leading-8 text-slate-800">
                {preview}
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
