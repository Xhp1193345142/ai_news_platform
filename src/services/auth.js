const SESSION_KEY = "ai-signal.session";
const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1").replace(/\/$/, "");

async function request(path, options = {}) {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers ?? {}) },
    ...options,
  });
  if (response.status === 204) return null;
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail ?? "请求未能完成，请稍后重试");
  return payload;
}

export function getStoredSession() {
  try {
    return JSON.parse(localStorage.getItem(SESSION_KEY) ?? "null");
  } catch {
    localStorage.removeItem(SESSION_KEY);
    return null;
  }
}

export function storeSession(session) {
  localStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

export function clearSession() {
  localStorage.removeItem(SESSION_KEY);
}

export async function authenticate(mode, { email, password }) {
  const endpoint = mode === "login" ? "/auth/login" : "/auth/register";
  const session = await request(endpoint, {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  storeSession(session);
  return session;
}

export async function fetchCurrentUser(accessToken) {
  return request("/me", { headers: { Authorization: `Bearer ${accessToken}` } });
}

export async function refreshSession(refreshToken) {
  const session = await request("/auth/refresh", {
    method: "POST",
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  storeSession(session);
  return session;
}

export async function revokeSession(refreshToken) {
  if (!refreshToken) {
    clearSession();
    return;
  }
  try {
    await request("/auth/logout", { method: "POST", body: JSON.stringify({ refresh_token: refreshToken }) });
  } finally {
    clearSession();
  }
}
