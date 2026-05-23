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

export async function uploadDocument(accessToken: string, file: File, confirmedDemo: boolean) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("confirm_no_real_client_data", String(confirmedDemo));

  const response = await fetch(`${API_BASE}/documents`, {
    method: "POST",
    headers: {Authorization: `Bearer ${accessToken}`},
    body: formData,
  });

  if (!response.ok) {
    const problem = await response.json().catch(() => null);
    throw new Error(problem?.title ?? "تعذر رفع المستند");
  }

  return response.json();
}

export async function getDocumentStatus(accessToken: string, docId: string) {
  const response = await fetch(`${API_BASE}/documents/${docId}/status`, {
    headers: {Authorization: `Bearer ${accessToken}`},
    cache: "no-store",
  });
  if (!response.ok) {
    const problem = await response.json().catch(() => null);
    throw new Error(problem?.title ?? "تعذر تحميل حالة المستند");
  }
  return response.json();
}

export async function getDocument(accessToken: string, docId: string) {
  const response = await fetch(`${API_BASE}/documents/${docId}`, {
    headers: {Authorization: `Bearer ${accessToken}`},
    cache: "no-store",
  });
  if (!response.ok) {
    const problem = await response.json().catch(() => null);
    throw new Error(problem?.title ?? "تعذر تحميل المستند");
  }
  return response.json();
}
