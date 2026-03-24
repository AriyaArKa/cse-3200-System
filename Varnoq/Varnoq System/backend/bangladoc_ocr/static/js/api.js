import { state } from "./state.js";

export function apiBase(dom) {
  const base = (dom.apiBase.value || "").replace(/\/$/, "");
  return base;
}

export function apiUrl(dom, path) {
  return `${apiBase(dom)}${path}`;
}

export function authHeader() {
  if (!state.token) return {};
  return { Authorization: `Bearer ${state.token}` };
}

export async function apiFetch(dom, path, options = {}) {
  const headers = {
    ...(options.headers || {}),
    ...authHeader(),
  };
  return fetch(apiUrl(dom, path), { ...options, headers });
}
