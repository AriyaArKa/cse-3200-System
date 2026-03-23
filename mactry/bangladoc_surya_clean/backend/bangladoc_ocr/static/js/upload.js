import { apiFetch } from "./api.js";
import { state } from "./state.js";
import { sleep } from "./utils.js";
import { renderResults } from "./reports.js";
import { startPolling, stopPolling } from "./progress.js";
import { renderDocumentsList } from "./documents.js";

async function waitForJob(dom, jobId) {
  const maxPolls = 300;
  for (let i = 0; i < maxPolls; i += 1) {
    const res = await apiFetch(dom, `/jobs/${encodeURIComponent(jobId)}`);
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || `Job ${jobId} failed to load`);
    }
    const status = String(data.status || "").toLowerCase();
    if (status === "done") return data;
    if (status === "failed") {
      throw new Error(data.error_msg || `Job ${jobId} failed`);
    }
    await sleep(1000);
  }
  throw new Error(`Job ${jobId} timed out`);
}

async function fetchReport(dom, docId) {
  const res = await apiFetch(dom, `/documents/${encodeURIComponent(docId)}/report`);
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || `Report not available for ${docId}`);
  }
  return data;
}

async function runJobsAndCollectReports(dom, jobs) {
  const reports = [];
  for (let i = 0; i < jobs.length; i += 1) {
    const job = jobs[i];
    dom.progressText.textContent = `Waiting for job ${i + 1}/${jobs.length}...`;
    try {
      const done = await waitForJob(dom, job.job_id);
      const docId = done.document && done.document.doc_id ? done.document.doc_id : job.doc_id;
      const report = await fetchReport(dom, docId);
      reports.push(report);
    } catch (err) {
      reports.push({
        filename: job.doc_id || `job-${job.job_id}`,
        error: err.message,
      });
    }
  }
  return reports;
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

    const reports = await runJobsAndCollectReports(dom, jobs);
    dom.progressBar.style.width = "100%";
    dom.progressText.textContent = "Processing complete.";
    renderResults(dom, { documents: reports });
    await renderDocumentsList(dom);
  } catch (err) {
    dom.error.textContent = err.message;
  } finally {
    stopPolling();
  }
}
