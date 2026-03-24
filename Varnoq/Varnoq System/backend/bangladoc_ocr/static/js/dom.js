export function bindDom() {
  return {
    apiBase: document.getElementById("apiBase"),
    email: document.getElementById("email"),
    password: document.getElementById("password"),
    registerBtn: document.getElementById("registerBtn"),
    loginBtn: document.getElementById("loginBtn"),
    logoutBtn: document.getElementById("logoutBtn"),
    authStatus: document.getElementById("authStatus"),
    dropzone: document.getElementById("dropzone"),
    fileInput: document.getElementById("fileInput"),
    fileLabel: document.getElementById("fileLabel"),
    selectedFilesList: document.getElementById("selectedFilesList"),
    domain: document.getElementById("domain"),
    uploadBtn: document.getElementById("uploadBtn"),
    refreshDocsBtn: document.getElementById("refreshDocsBtn"),
    docsList: document.getElementById("docsList"),
    progressBar: document.getElementById("progressBar"),
    progressText: document.getElementById("progressText"),
    error: document.getElementById("error"),
    results: document.getElementById("results"),
  };
}
