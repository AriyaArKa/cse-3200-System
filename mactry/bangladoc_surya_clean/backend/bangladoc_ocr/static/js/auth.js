import { state } from "./state.js";
import { apiFetch, apiUrl } from "./api.js";

async function parseResponseError(res, fallbackMessage) {
  const contentType = (res.headers.get("content-type") || "").toLowerCase();
  if (contentType.includes("application/json")) {
    const data = await res.json();
    return data.detail || fallbackMessage;
  }
  const text = await res.text();
  return text || fallbackMessage;
}

export function setAuthStatus(dom, message, isError = false) {
  dom.authStatus.textContent = message;
  dom.authStatus.className = isError ? "error" : "muted";
}

export function saveToken(token) {
  state.token = token || "";
  if (state.token) {
    localStorage.setItem("bangladoc_token", state.token);
  } else {
    localStorage.removeItem("bangladoc_token");
  }
}

export async function refreshSession(dom) {
  if (!state.token) {
    state.user = null;
    setAuthStatus(dom, "Not logged in.");
    return;
  }

  try {
    const res = await apiFetch(dom, "/auth/me");
    if (!res.ok) throw new Error("Session expired");
    state.user = await res.json();
    setAuthStatus(dom, `Logged in as ${state.user.email} (${state.user.role})`);
  } catch (_) {
    saveToken("");
    state.user = null;
    setAuthStatus(dom, "Not logged in.");
  }
}

export async function register(dom) {
  const email = (dom.email.value || "").trim();
  const password = dom.password.value || "";
  if (!email || !password) {
    setAuthStatus(dom, "Email and password are required.", true);
    return;
  }

  try {
    const res = await fetch(apiUrl(dom, "/auth/register"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      throw new Error(await parseResponseError(res, "Register failed"));
    }
    const data = await res.json();
    setAuthStatus(dom, `Registered ${data.email}. Now click Login.`);
  } catch (err) {
    setAuthStatus(dom, err.message, true);
  }
}

export async function login(dom) {
  const email = (dom.email.value || "").trim();
  const password = dom.password.value || "";
  if (!email || !password) {
    setAuthStatus(dom, "Email and password are required.", true);
    return;
  }

  try {
    const res = await fetch(apiUrl(dom, "/auth/login"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      throw new Error(await parseResponseError(res, "Login failed"));
    }
    const data = await res.json();
    saveToken(data.access_token);
    await refreshSession(dom);
  } catch (err) {
    setAuthStatus(dom, err.message, true);
  }
}

export function logout(dom) {
  saveToken("");
  state.user = null;
  setAuthStatus(dom, "Logged out.");
}
