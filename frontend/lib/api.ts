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

export async function confirmDocument(
  accessToken: string,
  docId: string,
  overrides: {title_ar?: string; doc_type?: string; practice_area?: string[]},
) {
  const response = await fetch(`${API_BASE}/documents/${docId}/confirm`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(overrides),
  });
  if (!response.ok) {
    const problem = await response.json().catch(() => null);
    throw new Error(problem?.title ?? "تعذر تأكيد المستند");
  }
  return response.json();
}

export async function searchRegulations(accessToken: string, query: string) {
  const response = await fetch(`${API_BASE}/search?q=${encodeURIComponent(query)}`, {
    headers: {Authorization: `Bearer ${accessToken}`},
    cache: "no-store",
  });
  if (!response.ok) {
    const problem = await response.json().catch(() => null);
    throw new Error(problem?.title ?? "تعذر البحث");
  }
  return response.json();
}

export async function askRegulations(accessToken: string, question: string) {
  const response = await fetch(`${API_BASE}/search/ask`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({question}),
  });
  if (!response.ok) {
    const problem = await response.json().catch(() => null);
    throw new Error(problem?.title ?? "تعذر توليد الإجابة");
  }
  return response.json();
}

export async function askDocument(accessToken: string, docId: string, question: string) {
  const response = await fetch(`${API_BASE}/documents/${docId}/ask`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({question, language: "ar"}),
  });
  if (!response.ok) {
    const problem = await response.json().catch(() => null);
    throw new Error(problem?.title ?? "تعذر توليد الإجابة");
  }
  return response.json();
}
