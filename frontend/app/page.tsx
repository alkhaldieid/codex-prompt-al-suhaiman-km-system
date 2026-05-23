import { LoginForm } from "@/components/LoginForm";

export default function LoginPage() {
  return (
    <main className="relative flex min-h-screen items-center justify-center bg-slate-50 px-6">
      <LoginForm />
      <button className="absolute bottom-6 left-6 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700">
        العربية
      </button>
    </main>
  );
}
