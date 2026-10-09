"use strict";
const $ = (id) => document.getElementById(id);
const NS = "http://www.w3.org/2000/svg";
let file = null, objectUrl = null, limits = null;

function showError(msg) { $("error").textContent = msg || ""; $("error").hidden = !msg; }
function setBusy(b) { $("loading").hidden = !b; $("run-btn").disabled = b || !file; $("clear-btn").disabled = b || !file; }

function clearAll() {
  if (objectUrl) URL.revokeObjectURL(objectUrl);
  file = objectUrl = null;
  $("file-input").value = "";
  $("preview").removeAttribute("src");
  $("overlay").replaceChildren();
  $("text-out").value = "";
  $("blocks").tBodies[0].replaceChildren();
  $("warnings").replaceChildren();
  $("meta").textContent = "";
  $("preview-section").hidden = $("result-section").hidden = true;
  showError("");
  setBusy(false);
}

function choose(f) {
  clearAll();
  if (!f) return;
  if (limits && f.size > limits.max_upload_bytes) {
    showError(`File is ${f.size} bytes; the configured limit is ${limits.max_upload_bytes} bytes.`);
    return;
  }
  file = f;
  objectUrl = URL.createObjectURL(f);
  $("preview").src = objectUrl;
  $("preview-section").hidden = false;
  setBusy(false);
}

function drawBoxes(res) {
  const svg = $("overlay");
  svg.replaceChildren();
  if (!res.image_width) return;
  svg.setAttribute("viewBox", `0 0 ${res.image_width} ${res.image_height}`);
  for (const b of res.blocks) {
    let el;
    if (b.polygon) { el = document.createElementNS(NS, "polygon"); el.setAttribute("points", b.polygon.map((p) => p.join(",")).join(" ")); }
    else if (b.bbox2d) { const [x1, y1, x2, y2] = b.bbox2d; el = document.createElementNS(NS, "rect"); el.setAttribute("x", x1); el.setAttribute("y", y1); el.setAttribute("width", x2 - x1); el.setAttribute("height", y2 - y1); }
    if (el) svg.appendChild(el);
  }
}

function render(res) {
  for (const w of res.warnings || []) { const li = document.createElement("li"); li.textContent = w; $("warnings").appendChild(li); }
  if (res.status !== "succeeded") {
    showError(res.error ? `${res.error.code}: ${res.error.message}` : "OCR failed.");
    return;
  }
  const eng = res.engine ? `${res.engine.id}${res.engine.version ? " " + res.engine.version : ""} (${res.engine.locality})` : "unknown";
  $("meta").textContent = `Engine: ${eng} · ${res.processing_time_ms} ms · ${res.image_width}×${res.image_height}px · ${res.blocks.length} block(s)`;
  $("text-out").value = res.detected_text;
  const tb = $("blocks").tBodies[0];
  for (const b of res.blocks) {
    const tr = tb.insertRow();
    tr.insertCell().textContent = b.line_index;
    tr.insertCell().textContent = b.text;
    tr.insertCell().textContent = b.confidence == null ? "n/a" : b.confidence.toFixed(3);
    tr.insertCell().textContent = b.bbox2d ? b.bbox2d.join(", ") : "n/a";
  }
  drawBoxes(res);
  $("result-section").hidden = false;
}

async function run() {
  if (!file) return;
  showError(""); $("warnings").replaceChildren(); setBusy(true);
  const fd = new FormData();
  fd.append("file", file);
  try {
    const r = await fetch("/api/v1/ocr", { method: "POST", body: fd });
    render(await r.json());
  } catch (e) {
    showError("Could not reach the server.");
  } finally { setBusy(false); }
}

async function init() {
  try {
    const caps = await (await fetch("/api/v1/ocr/capabilities")).json();
    limits = caps.limits;
    const o = caps.ocr;
    $("engine-status").textContent = o.status === "available"
      ? `Engine: ${o.engine.id} (${o.engine.locality}) – ${o.model_loaded ? "model loaded" : "model loads on first run"}`
      : `OCR engine unavailable: ${o.reason || "unknown reason"}`;
  } catch (e) { $("engine-status").textContent = "Server not reachable."; }
}

$("file-input").addEventListener("change", (e) => choose(e.target.files[0]));
$("run-btn").addEventListener("click", run);
$("clear-btn").addEventListener("click", clearAll);
$("copy-btn").addEventListener("click", () => navigator.clipboard.writeText($("text-out").value));
const drop = $("drop");
drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
drop.addEventListener("dragleave", () => drop.classList.remove("over"));
drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); choose(e.dataTransfer.files[0]); });
init();
