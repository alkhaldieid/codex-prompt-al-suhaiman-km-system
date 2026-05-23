"use client";

import { useEffect, useState } from "react";
import { Bell, FileText, Search, Settings, Upload } from "lucide-react";
import { getMe } from "@/lib/api";

type User = {
  display_name_ar: string;
  email: string;
  role: string;
};

export function HomeShell() {
  const [user, setUser] = useState<User | null>(null);

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

  return (
    <main className="min-h-screen bg-slate-50">
      <header className="flex h-16 items-center justify-between border-b border-slate-200 bg-white px-8">
        <div className="text-xl font-bold text-slate-950">السحيمان</div>
        <div className="flex w-[42rem] max-w-[45vw] items-center gap-3 rounded-md border border-slate-300 bg-slate-50 px-4 py-2 text-slate-500">
          <Search aria-hidden="true" className="h-5 w-5" />
          <span>ابحث في السوابق والآراء والأنظمة…</span>
        </div>
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
            {["هيئة الخبراء", "ساما", "المنصة الوطنية"].map((source) => (
              <article key={source} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
                <div className="mb-2 text-xs font-semibold text-accent-dark">{source}</div>
                <h3 className="line-clamp-2 text-sm font-semibold leading-6 text-slate-900">
                  ستظهر هنا التحديثات التنظيمية بعد تفعيل المتصلين
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
            <div className="flex items-center gap-3 rounded-lg border border-slate-300 bg-white px-4 py-4">
              <Search className="h-6 w-6 text-slate-500" aria-hidden="true" />
              <input
                className="w-full border-0 text-lg outline-none"
                placeholder="ابحث في السوابق والآراء والأنظمة…"
                aria-label="البحث"
              />
            </div>
            <div className="mt-5 flex flex-wrap gap-2">
              {["سوابق قضائية", "آراء قانونية", "أنظمة ولوائح", "نماذج"].map((chip) => (
                <button key={chip} className="rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50">
                  {chip}
                </button>
              ))}
            </div>
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
