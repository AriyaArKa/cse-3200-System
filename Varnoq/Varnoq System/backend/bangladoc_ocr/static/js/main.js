import { bindDom } from "./dom.js";
import { state } from "./state.js";
import { getDefaultBase } from "./utils.js";
import { addFiles, renderSelectedFiles } from "./files.js";
import { login, logout, refreshSession, register, saveToken } from "./auth.js";
import { upload } from "./upload.js";
import { renderDocumentsList } from "./documents.js";

const dom = bindDom();

function wireDropzone() {
  dom.dropzone.addEventListener("click", () => dom.fileInput.click());

  dom.fileInput.addEventListener("change", (event) => {
    addFiles(dom, event.target.files);
    event.target.value = "";
  });

  dom.dropzone.addEventListener("dragover", (event) => {
    event.preventDefault();
    dom.dropzone.classList.add("dragover");
  });

  dom.dropzone.addEventListener("dragleave", () => {
    dom.dropzone.classList.remove("dragover");
  });

  dom.dropzone.addEventListener("drop", (event) => {
    event.preventDefault();
    dom.dropzone.classList.remove("dragover");
    if (event.dataTransfer.files && event.dataTransfer.files.length) {
      addFiles(dom, event.dataTransfer.files);
    }
  });
}

function wireActions() {
  dom.registerBtn.addEventListener("click", async () => {
    await register(dom);
  });

  dom.loginBtn.addEventListener("click", async () => {
    await login(dom);
    await renderDocumentsList(dom);
  });

  dom.logoutBtn.addEventListener("click", () => {
    logout(dom);
    renderDocumentsList(dom);
  });

  dom.uploadBtn.addEventListener("click", async () => {
    await upload(dom);
  });

  dom.refreshDocsBtn.addEventListener("click", async () => {
    await renderDocumentsList(dom);
  });
}

async function init() {
  dom.apiBase.value = getDefaultBase();
  state.token = localStorage.getItem("bangladoc_token") || "";
  saveToken(state.token);
  renderSelectedFiles(dom);
  wireDropzone();
  wireActions();
  await refreshSession(dom);
  await renderDocumentsList(dom);
}

init();
