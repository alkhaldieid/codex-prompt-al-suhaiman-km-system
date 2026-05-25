"use client";

import { useState } from "react";
import { LockKeyhole, Mail } from "lucide-react";
import { login } from "@/lib/api";

export function LoginForm() {
  const [email, setEmail] = useState("lawyer.a@demo.suhaiman.sa");
  const [password, setPassword] = useState("DemoPass123!");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const tokens = await login(email, password);
      window.localStorage.setItem("suhaiman_access_token", tokens.access_token);
      window.location.href = "/home";
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر تسجيل الدخول");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="w-full max-w-[400px] rounded-lg border border-slate-200 bg-white p-8 shadow-sm">
      <div className="mb-8 text-center">
        <div className="text-3xl font-bold text-slate-950">السحيمان</div>
        <p className="mt-2 text-sm text-slate-600">مكتبة الأنظمة والسوابق</p>
      </div>

      <label className="mb-2 block text-sm font-medium text-slate-800" htmlFor="email">
        البريد الإلكتروني
      </label>
      <div className="mb-4 flex items-center gap-2 rounded-md border border-slate-300 bg-white px-3">
        <Mail aria-hidden="true" className="h-4 w-4 text-slate-500" />
        <input
          id="email"
          dir="ltr"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          className="h-11 w-full border-0 bg-transparent text-left outline-none"
          autoComplete="email"
          required
        />
      </div>

      <label className="mb-2 block text-sm font-medium text-slate-800" htmlFor="password">
        كلمة المرور
      </label>
      <div className="mb-4 flex items-center gap-2 rounded-md border border-slate-300 bg-white px-3">
        <LockKeyhole aria-hidden="true" className="h-4 w-4 text-slate-500" />
        <input
          id="password"
          dir="ltr"
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          className="h-11 w-full border-0 bg-transparent text-left outline-none"
          autoComplete="current-password"
          required
        />
      </div>

      {error ? <div role="alert" className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}

      <button
        type="submit"
        disabled={loading}
        className="h-11 w-full rounded-md bg-accent font-semibold text-white transition hover:bg-accent-dark disabled:cursor-not-allowed disabled:opacity-70"
      >
        {loading ? "جارٍ تسجيل الدخول…" : "تسجيل الدخول"}
      </button>

      <a href="#" className="mt-5 block text-center text-sm text-accent-dark">
        نسيت كلمة المرور؟
      </a>
    </form>
  );
}
