// Thin client for the FastAPI backend. Same-origin in production; VITE_API_URL in development.
const BASE = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

async function request(method, path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = data && data.detail;
    const message = Array.isArray(detail) ? detail.map((d) => d.msg).join("; ") : detail || res.statusText;
    throw new Error(message);
  }
  return data;
}

export const api = {
  health: () => request("GET", "/health"),
  taxonomy: () => request("GET", "/taxonomy"),
  locations: () => request("GET", "/locations"),
  complaints: (params) => request("GET", `/complaints?${new URLSearchParams(params)}`),
  complaint: (id) => request("GET", `/complaints/${id}`),
  submit: (body) => request("POST", "/complaints", body),
  review: (id, body) => request("POST", `/complaints/${id}/review`, body),
  metrics: () => request("GET", "/metrics"),
  audit: (params) => request("GET", `/audit?${new URLSearchParams(params)}`),
};
