import { apiFetch } from "./api.js";
import { escapeHtml, formatDuration, normalizeEngine } from "./utils.js";

export async function markVerified(dom, docId, pageNumber, verified, button) {
  button.disabled = true;
  try {
    const res = await apiFetch(dom, "/corpus/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ doc_id: docId, page_number: pageNumber, verified }),
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || "Verification failed");
    }
    button.textContent = verified ? "Verified" : "Mark as Verified";
  } catch (err) {
    alert(`Verify update failed: ${err.message}`);
  } finally {
    button.disabled = false;
  }
}

export function renderResults(dom, payload) {
  const docs = payload.documents || [];
  if (!docs.length) {
    dom.results.innerHTML = "<div class='muted'>No results returned.</div>";
    return;
  }

  let html = "";
  const globalRows = [];
  docs.forEach((doc, idx) => {
    if (doc.error) {
      html += `<div class="error">${doc.filename || "file"}: ${doc.error}</div>`;
      globalRows.push(
        `<div class="global-row"><span>${escapeHtml(doc.filename || `Document ${idx + 1}`)}</span><span class="error">Failed</span></div>`
      );
      return;
    }

    const docId = doc.doc_id || "";
    const sourceName = (doc.document && doc.document.source) || doc.filename || `Document ${idx + 1}`;
    const pages = Array.isArray(doc.pages) ? [...doc.pages] : [];
    pages.sort((a, b) => (a.page_number || 0) - (b.page_number || 0));

    const expectedPagesRaw = doc.document && Number(doc.document.total_pages);
    const expectedPages = Number.isFinite(expectedPagesRaw) && expectedPagesRaw > 0 ? expectedPagesRaw : pages.length;
    const processingMs = doc.document && doc.document.processing_summary
      ? Number(doc.document.processing_summary.processing_time_ms || 0)
      : 0;
    const processingTime = formatDuration(processingMs);

    const presentSet = new Set(pages.map((p) => Number(p.page_number || 0)).filter((n) => n > 0));
    const presentPages = Array.from(presentSet).sort((a, b) => a - b);

    const missingPages = [];
    for (let p = 1; p <= expectedPages; p += 1) {
      if (!presentSet.has(p)) missingPages.push(p);
    }

    const completion = `${presentPages.length}/${expectedPages}`;
    const status = missingPages.length ? `Missing ${missingPages.length}` : "Complete";
    globalRows.push(
      `<div class="global-row"><span>${escapeHtml(sourceName)}</span><span class="muted">${completion} pages · ${status} · ${processingTime}</span></div>`
    );

    let pageIndexHtml = "";
    if (expectedPages <= 120) {
      for (let p = 1; p <= expectedPages; p += 1) {
        if (presentSet.has(p)) {
          pageIndexHtml += `<a class="chip ok" href="#doc-${idx}-page-${p}">P${p}</a>`;
        } else {
          pageIndexHtml += `<span class="chip miss">P${p}</span>`;
        }
      }
    } else {
      pageIndexHtml = `<span class="muted">Document has ${expectedPages} pages. Use page cards below to review.</span>`;
    }

    html += `
      <div class="doc-block">
        <div class="meta" style="margin-bottom:10px;">
          <strong>${escapeHtml(sourceName)}</strong>
          <span class="muted">doc_id: ${escapeHtml(docId)}</span>
          <span class="muted">pages returned: ${presentPages.length}</span>
        </div>
        <div class="doc-summary">
          <div class="summary-box">
            <div class="k">Page Coverage</div>
            <div class="v">${completion}</div>
          </div>
          <div class="summary-box">
            <div class="k">Status</div>
            <div class="v">${missingPages.length ? `Missing: ${missingPages.join(", ")}` : "All pages present"}</div>
          </div>
          <div class="summary-box">
            <div class="k">Processing Time</div>
            <div class="v">${processingTime}</div>
          </div>
        </div>
        <div class="doc-index">
          <div class="muted">Quick page check</div>
          <div class="chip-wrap">${pageIndexHtml}</div>
        </div>
    `;

    pages.forEach((page, pageIdx) => {
      const engine = (page.extraction && page.extraction.engine) || "unknown";
      const tag = normalizeEngine(engine);
      const score = page.extraction && typeof page.extraction.confidence_score === "number"
        ? page.extraction.confidence_score.toFixed(4)
        : "0.0000";
      const safeText = escapeHtml(page.full_text || "");
      const decisions = Array.isArray(page.decisions) ? page.decisions : [];
      const decisionsHtml = decisions.length
        ? decisions.map((d) => {
            const detail = escapeHtml(d.detail || "");
            const keyword = escapeHtml(d.keyword || "DECISION");
            const sev = escapeHtml(d.severity || "info");
            return `<div class="muted" style="margin-top:4px;">[${sev}] ${keyword}: ${detail}</div>`;
          }).join("")
        : `<div class="muted" style="margin-top:4px;">No decision log available.</div>`;
      const verified = !!page.verified;
      const pn = Number(page.page_number || 0);

      html += `
        <details class="page-details" ${pageIdx === 0 ? "open" : ""} id="doc-${idx}-page-${pn}">
          <summary>
            <div class="meta" style="margin-bottom:0;">
              <strong>Page ${pn}</strong>
              <span class="badge ${tag}">${engine}</span>
              <span class="muted">Confidence: ${score}</span>
              <span class="muted">${verified ? "Verified" : "Not verified"}</span>
            </div>
          </summary>
          <div class="result-page" style="margin-top:8px;">
            <div class="text-box">${safeText || "(empty)"}</div>
            <details style="margin-top:8px;">
              <summary class="muted">Show decisions</summary>
              <div style="margin-top:6px;">${decisionsHtml}</div>
            </details>
            <div class="row" style="margin-top:8px;">
              <button data-doc="${docId}" data-page="${pn}" data-verified="${verified ? "0" : "1"}">
                ${verified ? "Verified" : "Mark as Verified"}
              </button>
            </div>
          </div>
        </details>
      `;
    });

    html += "</div>";
  });

  if (globalRows.length) {
    html = `
      <div class="global-summary">
        <strong>Documents Overview</strong>
        <div style="margin-top:6px;">${globalRows.join("")}</div>
      </div>
    ` + html;
  }

  dom.results.innerHTML = html;
  dom.results.querySelectorAll("button[data-doc]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const docId = btn.getAttribute("data-doc");
      const page = Number(btn.getAttribute("data-page"));
      const target = btn.getAttribute("data-verified") === "1";
      markVerified(dom, docId, page, target, btn);
      btn.setAttribute("data-verified", target ? "0" : "1");
    });
  });
}
