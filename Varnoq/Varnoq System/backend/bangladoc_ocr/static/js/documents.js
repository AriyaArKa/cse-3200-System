import { apiFetch } from "./api.js";
import { state } from "./state.js";
import { escapeHtml } from "./utils.js";
import { renderResults } from "./reports.js";

async function cancelDocument(dom, docId) {
  const res = await apiFetch(dom, `/documents/${encodeURIComponent(docId)}/cancel`, {
    method: "POST",
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "Cancel failed");
  }
}

async function deleteDocument(dom, docId) {
  const res = await apiFetch(dom, `/documents/${encodeURIComponent(docId)}`, {
    method: "DELETE",
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "Delete failed");
  }
}

async function fetchReport(dom, docId) {
  const res = await apiFetch(dom, `/documents/${encodeURIComponent(docId)}/report`);
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || `Report not available for ${docId}`);
  }
  return data;
}

export async function renderDocumentsList(dom) {
  if (!state.token) {
    dom.docsList.innerHTML = "<div class='muted' style='padding:10px;'>Login to view your documents.</div>";
    return;
  }

  try {
    const res = await apiFetch(dom, "/documents");
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to list documents");

    const docs = data.documents || [];
    if (!docs.length) {
      dom.docsList.innerHTML = "<div class='muted' style='padding:10px;'>No documents uploaded yet.</div>";
      return;
    }

    dom.docsList.innerHTML = docs.map((doc) => {
      const canOpen = String(doc.status || "").toLowerCase() === "done";
      const canCancel = ["pending", "processing"].includes(String(doc.status || "").toLowerCase());
      const progressValue = Number.isFinite(Number(doc.progress_percent)) ? Number(doc.progress_percent) : 0;
      const progress = Math.max(0, Math.min(100, Math.round(progressValue)));
      const progressStatus = doc.progress_status ? ` | progress: ${escapeHtml(String(doc.progress_status))}` : "";
      return `
        <div class="docs-row">
          <div>
            <div><strong>${escapeHtml(doc.filename || "unknown")}</strong></div>
            <div class="muted">doc_id: ${escapeHtml(doc.doc_id)} | status: ${escapeHtml(doc.status)}${progressStatus}</div>
            <div class="doc-progress-wrap" aria-label="Document progress ${progress}%">
              <div class="doc-progress-fill" style="width:${progress}%;"></div>
            </div>
            <div class="muted">${progress}% complete</div>
          </div>
          <div style="display:flex;gap:8px;">
            <button type="button" data-open-doc="${escapeHtml(doc.doc_id)}" ${canOpen ? "" : "disabled"}>Open report</button>
            <button type="button" data-cancel-doc="${escapeHtml(doc.doc_id)}" ${canCancel ? "" : "disabled"}>Stop</button>
            <button type="button" data-delete-doc="${escapeHtml(doc.doc_id)}">Delete</button>
          </div>
        </div>
      `;
    }).join("");

    dom.docsList.querySelectorAll("button[data-open-doc]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const docId = btn.getAttribute("data-open-doc");
        btn.disabled = true;
        try {
          const report = await fetchReport(dom, docId);
          renderResults(dom, { documents: [report] });
          dom.error.textContent = "";
        } catch (err) {
          dom.error.textContent = err.message;
        } finally {
          btn.disabled = false;
        }
      });
    });

    dom.docsList.querySelectorAll("button[data-cancel-doc]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const docId = btn.getAttribute("data-cancel-doc");
        btn.disabled = true;
        try {
          await cancelDocument(dom, docId);
          await renderDocumentsList(dom);
          dom.error.textContent = "";
        } catch (err) {
          dom.error.textContent = err.message;
          btn.disabled = false;
        }
      });
    });

    dom.docsList.querySelectorAll("button[data-delete-doc]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const docId = btn.getAttribute("data-delete-doc");
        const ok = window.confirm("Delete this document and all outputs?");
        if (!ok) return;

        btn.disabled = true;
        try {
          await deleteDocument(dom, docId);
          await renderDocumentsList(dom);
          dom.results.innerHTML = "<div class='muted'>No OCR result yet.</div>";
          dom.error.textContent = "";
        } catch (err) {
          dom.error.textContent = err.message;
          btn.disabled = false;
        }
      });
    });
  } catch (err) {
    dom.docsList.innerHTML = `<div class='error' style='padding:10px;'>${escapeHtml(err.message)}</div>`;
  }
}
