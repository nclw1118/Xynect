const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, init);
  if (!res.ok) {
    // Extract FastAPI's `detail` field when available; fall back to raw text.
    let message = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") {
        message = body.detail;
      } else if (typeof body?.detail !== "undefined") {
        message = JSON.stringify(body.detail);
      }
    } catch {
      message = (await res.text().catch(() => "")) || message;
    }
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}
