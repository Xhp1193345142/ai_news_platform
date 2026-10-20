import { getStoredSession } from "./auth";

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1").replace(/\/$/, "");

async function api(path) {
  const token = getStoredSession()?.access_token;
  const response = await fetch(`${apiBaseUrl}${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail ?? "资讯加载失败");
  return payload;
}

export function fetchArticles(category = "全部") {
  const query = new URLSearchParams({ limit: "20" });
  if (category !== "全部") query.set("category", category);
  return api(`/articles?${query}`);
}
export function fetchArticle(id) { return api(`/articles/${id}`); }
export function fetchSources() { return api("/sources"); }
