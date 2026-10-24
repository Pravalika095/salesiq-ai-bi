// Central API client. Every backend call goes through `request`.
export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch {
    throw new ApiError(
      `Cannot reach the SalesIQ API at ${API_BASE_URL}. Is the backend running?`,
      0
    );
  }

  let body = null;
  try {
    body = await response.json();
  } catch {
    /* non-JSON body */
  }

  if (!response.ok) {
    const detail = body?.details?.length ? ` (${body.details.join("; ")})` : "";
    throw new ApiError((body?.error || `Request failed with status ${response.status}`) + detail, response.status);
  }
  return body;
}

export const api = {
  health: () => request("/api/health"),
  summary: () => request("/api/summary"),
  ask: (question) => request("/api/ask", { method: "POST", body: JSON.stringify({ question }) }),
  monthly: () => request("/api/analytics/monthly"),
  products: () => request("/api/analytics/products"),
  regions: () => request("/api/analytics/regions"),
  categories: () => request("/api/analytics/categories"),
  channels: () => request("/api/analytics/channels"),
  dataQuality: () => request("/api/data-quality"),
  transactionFilters: () => request("/api/transactions/filters"),
  transactions: (params) => {
    const query = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== "" && v !== null && v !== undefined)
    );
    return request(`/api/transactions?${query}`);
  },
};
