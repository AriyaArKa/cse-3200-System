export function getDefaultBase() {
  if (window.location.protocol === "http:" || window.location.protocol === "https:") {
    return window.location.origin;
  }
  return "http://localhost:8000";
}

export function fileId(file) {
  return `${file.name}::${file.size}::${file.lastModified}`;
}

export function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export function formatDuration(ms) {
  const value = Number(ms || 0);
  if (!Number.isFinite(value) || value <= 0) return "n/a";
  if (value < 1000) return `${Math.round(value)} ms`;
  const sec = value / 1000;
  if (sec < 60) return `${sec.toFixed(2)} s`;
  const min = Math.floor(sec / 60);
  const rem = sec % 60;
  return `${min}m ${rem.toFixed(1)}s`;
}

export function escapeHtml(text) {
  return String(text || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function normalizeEngine(engine) {
  const e = (engine || "unknown").toLowerCase();
  if (e.includes("pymupdf") || e.includes("digital")) return "digital";
  if (e.includes("easy")) return "easyocr";
  if (e.includes("paddle")) return "paddleocr";
  if (e.includes("gemini")) return "gemini";
  if (e.includes("ollama")) return "ollama";
  return "digital";
}

export function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
