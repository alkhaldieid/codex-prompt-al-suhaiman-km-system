"use client";

import { useEffect, useState } from "react";
import { Bell, FileText, Loader2, Search, Settings, Upload } from "lucide-react";
import { getMe } from "@/lib/api";

type User = {
  display_name_ar: string;
  email: string;
  role: string;
};

export function HomeShell() {
  const [user, setUser] = useState<User | null>(null);
  const [query, setQuery] = useState("اللائحة التنفيذية لنظام العمل");
  const [results, setResults] = useState<any[]>([]);
  const [answer, setAnswer] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

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

  async function runSearch(event?: React.FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    if (!query.trim()) return;
    // Delegate to the full search page so all results, filters, and the
    // doc-viewer flow are reachable from the home search box.
    window.location.href = `/search?q=${encodeURIComponent(query.trim())}`;
  }

  return (
    <main className="min-h-screen bg-slate-50">
      <header className="flex h-16 items-center justify-between border-b border-slate-200 bg-white px-8">
        <div className="text-xl font-bold text-slate-950">السحيمان</div>
        <form onSubmit={runSearch} className="flex w-[42rem] max-w-[45vw] items-center gap-3 rounded-md border border-slate-300 bg-slate-50 px-4 py-2 text-slate-500">
          <Search aria-hidden="true" className="h-5 w-5" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="w-full border-0 bg-transparent outline-none"
            placeholder="ابحث في السوابق والآراء والأنظمة…"
            aria-label="البحث"
          />
        </form>
        <div className="flex items-center gap-3">
          <button aria-label="الإشعارات" className="rounded-md p-2 text-slate-600 hover:bg-slate-100">
            <Bell className="h-5 w-5" />
          </button>
          <button aria-label="الإعدادات" className="rounded-md p-2 text-slate-600 hover:bg-slate-100">
            <Settings className="h-5 w-5" />
          </button>
          <div className="text-sm">
            <div className="font-semibold text-slate-900">{user?.display_name_ar ?? "..."}</div>
            <div dir="ltr" className="text-slate-500">{user?.email ?? ""}</div>
          </div>
        </div>
      </header>

      <section className="grid grid-cols-[320px_minmax(0,1fr)_280px] gap-6 px-8 py-8">
        <aside className="order-1">
          <h2 className="mb-4 text-lg font-semibold text-slate-950">آخر التحديثات التنظيمية</h2>
          <div className="space-y-3">
            {["هيئة الخبراء", "أم القرى", "ساما", "سوق المال", "الزكاة والضريبة"].map((source) => (
              <article key={source} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
                <div className="mb-2 text-xs font-semibold text-accent-dark">{source}</div>
                <h3 className="line-clamp-2 text-sm font-semibold leading-6 text-slate-900">
                  مصدر تنظيمي رسمي مضاف إلى فهرس المعرفة
                </h3>
                <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
                  <span>2026-05-23</span>
                  <a className="font-semibold text-accent-dark" href="#">اقرأ</a>
                </div>
              </article>
            ))}
          </div>
        </aside>

        <section className="order-2">
          <div className="rounded-lg border border-slate-200 bg-white p-8 shadow-sm">
            <h1 className="mb-5 text-2xl font-bold text-slate-950">مرحباً بك في نظام المعرفة القانونية</h1>
            <form onSubmit={runSearch} className="flex items-center gap-3 rounded-lg border border-slate-300 bg-white px-4 py-4">
              <Search className="h-6 w-6 text-slate-500" aria-hidden="true" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                className="w-full border-0 text-lg outline-none"
                placeholder="ابحث في السوابق والآراء والأنظمة…"
                aria-label="البحث"
              />
              <button className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-accent-dark">
                بحث
              </button>
            </form>
            <div className="mt-5 flex flex-wrap gap-2">
              {["نظام العمل", "غسل الأموال", "حوكمة الشركات", "الزكاة", "حماية البيانات"].map((chip) => (
                <button key={chip} onClick={() => setQuery(chip)} className="rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50">
                  {chip}
                </button>
              ))}
            </div>

            <button
              onClick={() => runSearch()}
              disabled={busy}
              className="mt-5 flex items-center gap-2 rounded-md bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
            >
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
              اسأل الفهرس التنظيمي
            </button>

            {error ? <div role="alert" className="mt-5 rounded-lg bg-red-50 p-4 text-red-700">{error}</div> : null}

            {answer ? (
              <section className="mt-6 rounded-lg border border-teal-100 bg-teal-50 p-5 text-teal-950">
                <h2 className="mb-3 font-semibold">إجابة من الفهرس التنظيمي</h2>
                <p className="whitespace-pre-wrap leading-8">{answer}</p>
              </section>
            ) : null}

            {results.length ? (
              <section className="mt-6 space-y-3">
                <h2 className="font-semibold text-slate-950">نتائج البحث</h2>
                {results.map((result) => (
                  <article key={`${result.doc_id}-${result.snippet_ar}`} className="rounded-lg border border-slate-200 bg-white p-4">
                    <div className="mb-2 text-xs font-semibold text-accent-dark">{result.source_track}</div>
                    <h3 className="font-semibold leading-7 text-slate-950">{result.title_ar}</h3>
                    <p className="mt-2 font-textArabic text-lg leading-8 text-slate-700">{result.snippet_ar}</p>
                  </article>
                ))}
              </section>
            ) : null}
          </div>
        </section>

        <aside className="order-3">
          <h2 className="mb-4 text-lg font-semibold text-slate-950">نشاطك</h2>
          <div className="space-y-3">
            <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
              <Upload className="mb-3 h-5 w-5 text-accent-dark" />
              <div className="font-semibold">لا توجد عمليات رفع حديثة</div>
              <a href="/upload" className="mt-3 inline-block text-sm font-semibold text-accent-dark">
                رفع مستند جديد
              </a>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
              <FileText className="mb-3 h-5 w-5 text-accent-dark" />
              <div className="font-semibold">قائمة المراجعة فارغة</div>
            </div>
          </div>
        </aside>
      </section>
    </main>
  );
}
