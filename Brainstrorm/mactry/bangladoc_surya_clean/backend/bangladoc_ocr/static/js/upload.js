import { apiFetch } from "./api.js";
import { state } from "./state.js";
import { startPolling, stopPolling } from "./progress.js";
import { renderDocumentsList } from "./documents.js";

function scheduleDocumentsRefresh(dom) {
  let attempts = 0;
  const maxAttempts = 40;
  const intervalId = setInterval(async () => {
    attempts += 1;
    await renderDocumentsList(dom);
    if (attempts >= maxAttempts) {
      clearInterval(intervalId);
    }
  }, 3000);
}

export async function upload(dom) {
  if (!state.token) {
    dom.error.textContent = "Please login first.";
    return;
  }

  const selectedFiles = state.files.filter((f) => f.selected).map((f) => f.file);
  if (!selectedFiles.length) {
    dom.error.textContent = "Please select at least one PDF file.";
    return;
  }

  dom.error.textContent = "";
  dom.progressBar.style.width = "0%";
  dom.progressText.textContent = `Submitting ${selectedFiles.length} file(s)...`;
  startPolling(dom);

  const formData = new FormData();
  for (const file of selectedFiles) {
    formData.append("files", file);
  }
  formData.append("domain", dom.domain.value);

  try {
    const res = await apiFetch(dom, "/ocr", { method: "POST", body: formData });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Upload failed");
    }

    const jobs = Array.isArray(data.jobs) ? data.jobs : [];
    if (!jobs.length) {
      throw new Error("No OCR jobs were created.");
    }

    dom.progressBar.style.width = "100%";
    dom.progressText.textContent = `Queued ${jobs.length} job(s). Processing in background. Use My Documents to open report when done.`;
    await renderDocumentsList(dom);
    scheduleDocumentsRefresh(dom);
  } catch (err) {
    dom.error.textContent = err.message;
  } finally {
    stopPolling();
  }
}
