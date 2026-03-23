import { apiFetch } from "./api.js";
import { state } from "./state.js";
import { escapeHtml } from "./utils.js";
import { renderResults } from "./reports.js";

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
      return `
        <div class="docs-row">
          <div>
            <div><strong>${escapeHtml(doc.filename || "unknown")}</strong></div>
            <div class="muted">doc_id: ${escapeHtml(doc.doc_id)} | status: ${escapeHtml(doc.status)}</div>
          </div>
          <button type="button" data-open-doc="${escapeHtml(doc.doc_id)}" ${canOpen ? "" : "disabled"}>Open report</button>
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
  } catch (err) {
    dom.docsList.innerHTML = `<div class='error' style='padding:10px;'>${escapeHtml(err.message)}</div>`;
  }
}
