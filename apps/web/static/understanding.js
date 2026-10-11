"use strict";
/* Image understanding page. Talks only to the local VISTA server (POST /api/v1/understanding and its capabilities).
   The API key never reaches the browser: the server holds it. The image and the question are sent only after the user
   ticks the consent box; nothing is stored in the browser. */
(function () {
  const $ = (id) => document.getElementById(id);
  const URL_ASK = "/api/v1/understanding";
  const URL_CAPS = "/api/v1/understanding/capabilities";
  // Long on purpose: the provider can be slow. Keep it above VISTA_TASK_TIMEOUT_SECONDS (suggested 320 s) so the
  // server reports its own timeout error instead of the browser giving up first.
  const TIMEOUT_MS = 340000;
  let file = null;
  let objectUrl = null;
  let busy = false;
  let available = false;
  let ticker = null;

  function pill(text, cls) {
    $("provider-status").textContent = text;
    $("provider-status").className = "pill" + (cls ? " " + cls : "");
  }
  function showError(text) {
    $("error").textContent = text || "";
    $("error").hidden = !text;
  }
  function refresh() {
    $("ask-btn").disabled = busy || !file || !available;
    $("clear-btn").disabled = busy || !file;
    $("loading").hidden = !busy;
  }
  function startTicker() {
    const t0 = Date.now();
    $("loading").textContent = "Waiting for the provider… 0 s";
    ticker = setInterval(() => {
      $("loading").textContent = "Waiting for the provider… " + Math.round((Date.now() - t0) / 1000) + " s";
    }, 1000);
  }
  function stopTicker() {
    if (ticker !== null) clearInterval(ticker);
    ticker = null;
  }
  function clearResult() {
    $("answer").textContent = "";
    $("route").textContent = "";
    $("warnings").replaceChildren();
    $("result-section").hidden = true;
  }
  function clearAll() {
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    file = objectUrl = null;
    $("file-input").value = "";
    $("preview").removeAttribute("src");
    $("stage").hidden = true;
    clearResult();
    showError("");
    refresh();
  }
  function choose(f) {
    clearAll();
    if (!f) return;
    file = f;
    objectUrl = URL.createObjectURL(f);
    $("preview").src = objectUrl;
    $("stage").hidden = false;
    refresh();
  }

  async function loadCapabilities() {
    try {
      const ctl = new AbortController();
      const t = setTimeout(() => ctl.abort(), 4000);
      const r = await fetch(URL_CAPS, { signal: ctl.signal });
      clearTimeout(t);
      const u = (await r.json()).understanding;
      available = u.status === "available";
      if (available) {
        const p = u.provider || {};
        pill("Provider: " + (p.provider || "external") + " · " + (p.model || "model") + " · ready · timeout " +
          (p.timeout_seconds_per_attempt || "?") + " s per attempt", "ok");
      } else {
        pill("Provider: " + u.status, u.status === "disabled" ? "warn" : "bad");
        showError(u.reason || "The external provider is not available.");
      }
      if (u.policy_default && u.policy_default !== "local_only") $("mode-select").value = u.policy_default;
    } catch (_) {
      available = false;
      pill("Provider: unreachable", "bad");
    }
    refresh();
  }

  function render(body) {
    for (const w of body.warnings || []) {
      const li = document.createElement("li");
      li.textContent = w;
      $("warnings").appendChild(li);
    }
    const r = body.route;
    if (r) {
      $("route").textContent = "Route: mode " + r.mode + " → " + r.target + " (" + r.reason + ")" +
        (r.provider ? " · " + r.provider + (r.model ? " / " + r.model : "") : "") +
        " · image sent: " + (r.external_transmission ? "yes" : "no");
    }
    if (body.status !== "succeeded") {
      const e = body.error;
      showError(e ? e.code + ": " + e.message : "The request failed.");
      $("answer-title").hidden = true; // no empty "Answer" box when there is no answer
      $("answer").hidden = true;
      $("result-section").hidden = !r;
      return;
    }
    $("answer-title").hidden = false;
    $("answer").hidden = false;
    $("answer").textContent = body.answer;
    $("result-section").hidden = false;
  }

  async function ask() {
    if (!file || busy) return;
    showError("");
    clearResult();
    const mode = $("mode-select").value;
    if (!$("consent").checked) {
      showError("Tick the consent box first: the image and question are sent to NVIDIA only with your consent.");
      return;
    }
    const fd = new FormData();
    fd.append("file", file);
    fd.append("question", $("question").value);
    fd.append("mode", mode);
    fd.append("consent_external", "true");
    busy = true;
    refresh();
    startTicker();
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), TIMEOUT_MS);
    try {
      const resp = await fetch(URL_ASK, { method: "POST", body: fd, signal: ctl.signal });
      let body;
      try {
        body = await resp.json();
      } catch (_) {
        showError("The server sent an unexpected response (HTTP " + resp.status + ").");
        return;
      }
      render(body);
    } catch (e) {
      showError(e && e.name === "AbortError" ? "The browser stopped waiting (time limit)." : "Could not reach the server.");
    } finally {
      clearTimeout(timer);
      stopTicker();
      busy = false;
      refresh();
    }
  }

  $("file-input").addEventListener("change", (e) => choose(e.target.files[0]));
  $("ask-btn").addEventListener("click", ask);
  $("clear-btn").addEventListener("click", clearAll);
  const drop = $("drop");
  drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); choose(e.dataTransfer.files[0]); });
  window.addEventListener("pagehide", () => { stopTicker(); if (objectUrl) URL.revokeObjectURL(objectUrl); });
  refresh();
  loadCapabilities();
})();
