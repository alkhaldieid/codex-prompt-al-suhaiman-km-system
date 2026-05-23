export type LoginResponse = {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export async function login(email: string, password: string): Promise<LoginResponse> {
  const response = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({email, password}),
  });

  if (!response.ok) {
    const problem = await response.json().catch(() => null);
    throw new Error(problem?.title ?? "تعذر تسجيل الدخول");
  }

  return response.json();
}

export async function getMe(accessToken: string) {
  const response = await fetch(`${API_BASE}/auth/me`, {
    headers: {Authorization: `Bearer ${accessToken}`},
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("تعذر تحميل بيانات المستخدم");
  }
  return response.json();
}
