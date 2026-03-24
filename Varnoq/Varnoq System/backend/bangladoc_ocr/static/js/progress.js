import { state } from "./state.js";
import { apiFetch } from "./api.js";

export function setProgress(dom, current, total) {
  if (!total || total <= 0) {
    dom.progressBar.style.width = "0%";
    return;
  }
  const pct = Math.min(100, Math.round((current / total) * 100));
  dom.progressBar.style.width = `${pct}%`;
  dom.progressText.textContent = `Processing page ${current} of ${total}...`;
}

async function pollProgress(dom) {
  try {
    const res = await apiFetch(dom, "/ocr/progress");
    if (!res.ok) return;
    const payload = await res.json();
    if (payload.is_processing) {
      setProgress(dom, payload.current_page || 0, payload.total_pages || 0);
    }
  } catch (_) {
    // Keep UI responsive even if progress endpoint is temporarily unavailable.
  }
}

export function startPolling(dom) {
  stopPolling();
  state.progressTimer = setInterval(() => {
    pollProgress(dom);
  }, 500);
}

export function stopPolling() {
  if (state.progressTimer) {
    clearInterval(state.progressTimer);
    state.progressTimer = null;
  }
}
