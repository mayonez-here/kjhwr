const BASE = import.meta.env.VITE_API_BASE ?? "";

async function get(path, params = {}) {
  const qs = new URLSearchParams(params).toString();
  const res = await fetch(`${BASE}/api${path}${qs ? `?${qs}` : ""}`);
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body.detail) msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch { /* non-JSON error body */ }
    throw new Error(msg);
  }
  return res.json();
}

export const api = {
  meta: () => get("/meta"),
  decision: (delivery_date, cutoff) => get("/decision", { delivery_date, cutoff }),
  accuracy: (start, end, cutoff) => get("/accuracy", { start, end, cutoff }),
  horizon: (start, end) => get("/horizon", { start, end }),
};
