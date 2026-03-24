import { state } from "./state.js";
import { escapeHtml, fileId, formatSize } from "./utils.js";

export function renderSelectedFiles(dom) {
  if (!state.files.length) {
    dom.fileLabel.textContent = "No file selected";
    dom.selectedFilesList.innerHTML = "No files in queue.";
    return;
  }

  const selectedCount = state.files.filter((f) => f.selected).length;
  dom.fileLabel.textContent = `${selectedCount}/${state.files.length} selected`;

  let html = "";
  for (const entry of state.files) {
    const safeName = escapeHtml(entry.file.name);
    const checked = entry.selected ? "checked" : "";
    html += `
      <div class="file-item">
        <label class="muted" style="display:flex;align-items:center;gap:8px;">
          <input type="checkbox" data-file-toggle="${entry.id}" ${checked} />
          <span>${safeName} (${formatSize(entry.file.size)})</span>
        </label>
        <button type="button" data-file-remove="${entry.id}" style="padding:6px 8px;">Remove</button>
      </div>
    `;
  }
  dom.selectedFilesList.innerHTML = html;

  dom.selectedFilesList.querySelectorAll("input[data-file-toggle]").forEach((input) => {
    input.addEventListener("change", () => {
      const id = input.getAttribute("data-file-toggle");
      const entry = state.files.find((f) => f.id === id);
      if (entry) {
        entry.selected = input.checked;
        renderSelectedFiles(dom);
      }
    });
  });

  dom.selectedFilesList.querySelectorAll("button[data-file-remove]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.getAttribute("data-file-remove");
      state.files = state.files.filter((f) => f.id !== id);
      renderSelectedFiles(dom);
    });
  });
}

export function addFiles(dom, fileList) {
  const incoming = Array.from(fileList || []);
  if (!incoming.length) return;

  for (const file of incoming) {
    const isPdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
    if (!isPdf) continue;
    const id = fileId(file);
    if (state.files.some((f) => f.id === id)) continue;
    state.files.push({ id, file, selected: true });
  }

  renderSelectedFiles(dom);
}
