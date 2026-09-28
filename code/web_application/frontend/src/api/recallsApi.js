const BASE = "/api";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const error = new Error(body.detail || `Request failed (${res.status})`);
    error.status = res.status;
    throw error;
  }

  if (res.status === 204) return null;
  return res.json();
}

export function login(email, password) {
  return request("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function logout() {
  return request("/auth/logout", { method: "POST" });
}

export function me() {
  return request("/auth/me");
}

export function fetchRecalls(search = "") {
  const query = search ? `?search=${encodeURIComponent(search)}` : "";
  return request(`/recalls${query}`);
}

export function createRecall(payload) {
  return request("/recalls", { method: "POST", body: JSON.stringify(payload) });
}

export function updateRecall(id, payload) {
  return request(`/recalls/${id}`, { method: "PUT", body: JSON.stringify(payload) });
}

export function deleteRecall(id) {
  return request(`/recalls/${id}`, { method: "DELETE" });
}

export function deleteHighestRecall() {
  return request("/recalls/highest", { method: "DELETE" });
}
