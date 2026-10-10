"use strict";
/* Realtime Detection page. Glue between the DOM and VistaRT (realtime_core.js).
   Uses ONLY the existing endpoints: POST /api/v1/detection and GET /api/v1/detection/capabilities.
   Frames live in memory only: they are never stored, and nothing is sent anywhere except the local VISTA server. */
(function () {
  const RT = window.VistaRT;
  const $ = (id) => document.getElementById(id);
  const DETECTION_URL = "/api/v1/detection";
  const CAPS_URL = "/api/v1/detection/capabilities";
  const REQUEST_TIMEOUT_MS = 8000;
  const JPEG_QUALITY = 0.7;

  const video = $("video");
  const overlay = $("rt-overlay");
  const octx = overlay.getContext("2d");
  const grab = document.createElement("canvas");
  const gctx = grab.getContext("2d");

  const state = { detection: "idle", latest: null, failed: 0, rtts: [], serverMs: null, vfc: 0, timer: null };
  const videoMeter = RT.createRateMeter(3000);
  const inferMeter = RT.createRateMeter(5000);

  // ---------- small UI helpers ----------
  function pill(el, text, cls) {
    el.textContent = text;
    el.className = "pill" + (cls ? " " + cls : "");
  }
  function showMessage(text) {
    $("error").textContent = text || "";
    $("error").hidden = !text;
  }
  const fmt = (v, unit, digits) => (v == null ? "n/a" : v.toFixed(digits == null ? 1 : digits) + (unit || ""));

  function refreshUI() {
    const cam = camera.getState();
    const on = cam === "on";
    $("start-btn").disabled = cam === "starting" || on;
    $("stop-btn").disabled = !(on || cam === "starting");
    $("pause-btn").disabled = !on;
    $("pause-btn").textContent = state.detection === "paused" ? "Resume detection" : "Pause detection";
    $("placeholder").hidden = on;
    if (cam === "off") pill($("cam-status"), "Camera: off");
    else if (cam === "starting") pill($("cam-status"), "Camera: starting…", "warn");
    else if (cam === "error") pill($("cam-status"), "Camera: error", "bad");
    else if (state.detection === "paused") pill($("cam-status"), "Camera: on · detection paused", "warn");
    else pill($("cam-status"), "Camera: on · detecting", "ok");
  }

  function refreshStats() {
    $("stat-video-fps").textContent =
      "requestVideoFrameCallback" in HTMLVideoElement.prototype ? fmt(videoMeter.rate(), " fps") : "n/a (unsupported)";
    $("stat-infer-fps").textContent = fmt(inferMeter.rate(), " fps");
    $("stat-rtt").textContent = fmt(RT.median(state.rtts), " ms", 0);
    $("stat-server").textContent = fmt(state.serverMs, " ms", 0);
    $("stat-count").textContent = String(state.latest ? state.latest.detections.length : 0);
    $("stat-failed").textContent = String(state.failed);
  }

  function resetMeasurements() {
    videoMeter.reset();
    inferMeter.reset();
    state.rtts = [];
    state.serverMs = null;
    state.latest = null;
    state.failed = 0;
    drawOverlay();
    renderList();
    refreshStats();
  }

  // ---------- backend status ----------
  async function loadCapabilities() {
    try {
      const ctl = new AbortController();
      const t = setTimeout(() => ctl.abort(), 4000);
      const r = await fetch(CAPS_URL, { signal: ctl.signal });
      clearTimeout(t);
      const body = await r.json();
      const d = body.detection;
      if (d.status === "available") {
        pill($("be-status"), "Backend: ready · model " + (d.model_loaded ? "loaded" : "loads on first frame"), "ok");
        if (d.parameters && !state.latest) {
          const c = Number(d.parameters.confidence_threshold);
          if (Number.isFinite(c) && c >= 0.05 && c <= 0.95) {
            $("conf-range").value = String(c);
            $("conf-value").textContent = c.toFixed(2);
          }
        }
      } else {
        pill($("be-status"), "Backend: " + d.status, "bad");
        showMessage(d.reason || "The detection backend is not available.");
      }
    } catch (_) {
      pill($("be-status"), "Backend: unreachable", "bad");
    }
  }

  // ---------- capture + send ----------
  function capture() {
    if (video.readyState < 2 || !video.videoWidth) return Promise.resolve(null);
    const size = RT.captureSize(video.videoWidth, video.videoHeight, Number($("size-select").value));
    if (!size) return Promise.resolve(null);
    grab.width = size.width;
    grab.height = size.height;
    gctx.drawImage(video, 0, 0, size.width, size.height);
    return new Promise((resolve, reject) =>
      grab.toBlob((b) => (b ? resolve(b) : reject(new RT.RTError("capture", "JPEG encoding failed"))), "image/jpeg", JPEG_QUALITY)
    );
  }

  async function send(blob, signal) {
    const fd = new FormData();
    fd.append("file", blob, "frame.jpg");
    const conf = Number($("conf-range").value);
    const url = DETECTION_URL + "?confidence=" + encodeURIComponent(conf.toFixed(2));
    const ctl = new AbortController();
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      ctl.abort();
    }, REQUEST_TIMEOUT_MS);
    const onAbort = () => ctl.abort();
    if (signal) {
      if (signal.aborted) ctl.abort();
      else signal.addEventListener("abort", onAbort, { once: true });
    }
    try {
      let resp;
      try {
        resp = await fetch(url, { method: "POST", body: fd, signal: ctl.signal });
      } catch (e) {
        if (timedOut) throw new RT.RTError("timeout", "request timed out");
        if (e && e.name === "AbortError") throw e; // cancelled by stop(); the loop treats it as stale
        throw new RT.RTError("network", "cannot reach the server");
      }
      let body;
      try {
        body = await resp.json();
      } catch (e) {
        if (timedOut) throw new RT.RTError("timeout", "request timed out");
        if (e && e.name === "AbortError") throw e;
        throw new RT.RTError("invalid", "HTTP " + resp.status + " without a JSON body", { status: resp.status });
      }
      if (body && body.status && body.status !== "succeeded" && body.error) {
        throw new RT.RTError("http", body.error.message, { status: resp.status, code: body.error.code });
      }
      if (!resp.ok) throw new RT.RTError("http", "HTTP " + resp.status, { status: resp.status });
      const v = RT.validateResponse(body);
      if (!v.ok) throw new RT.RTError("invalid", v.reason);
      return body;
    } finally {
      clearTimeout(timer);
      if (signal) signal.removeEventListener("abort", onAbort);
    }
  }

  const loop = RT.createDetectionLoop({
    fps: Number($("fps-select").value),
    capture,
    send,
    onResult(result, info) {
      state.latest = result;
      state.serverMs = typeof result.processing_time_ms === "number" ? result.processing_time_ms : null;
      state.rtts.push(info.roundTripMs);
      if (state.rtts.length > 20) state.rtts.shift();
      inferMeter.mark();
      showMessage("");
      pill($("be-status"), "Backend: ready · model loaded", "ok");
      drawOverlay();
      renderList();
      refreshStats();
    },
    onError(err, info) {
      state.failed++;
      showMessage("Detection error: " + RT.describeBackendError(err).message + " The camera preview keeps running.");
      pill($("be-status"), "Backend: error (" + info.consecutiveErrors + " in a row)", "bad");
      if (info.consecutiveErrors >= 3) {
        state.latest = null; // do not keep showing boxes that are no longer current
        drawOverlay();
        renderList();
      }
      if (info.consecutiveErrors === 3) loadCapabilities();
      refreshStats();
    },
  });

  // ---------- overlay ----------
  function drawOverlay() {
    const dpr = window.devicePixelRatio || 1;
    const cw = overlay.clientWidth;
    const ch = overlay.clientHeight;
    if (overlay.width !== Math.round(cw * dpr) || overlay.height !== Math.round(ch * dpr)) {
      overlay.width = Math.round(cw * dpr);
      overlay.height = Math.round(ch * dpr);
    }
    octx.setTransform(dpr, 0, 0, dpr, 0, 0);
    octx.clearRect(0, 0, cw, ch);
    const res = state.latest;
    if (!res) return;
    const rect = RT.containRect(video.videoWidth, video.videoHeight, cw, ch);
    if (!rect) return;
    octx.font = "600 13px system-ui, sans-serif";
    octx.textBaseline = "top";
    octx.lineWidth = 2;
    for (const d of res.detections) {
      const m = RT.mapBox(d.bbox2d, res.image_width, res.image_height, rect);
      if (!m) continue;
      const color = "hsl(" + ((d.class_id * 47) % 360) + ",85%,50%)";
      octx.strokeStyle = color;
      octx.strokeRect(m.x, m.y, m.w, m.h);
      const text = d.label + " " + (d.confidence * 100).toFixed(0) + "%";
      const tw = octx.measureText(text).width + 8;
      const ty = m.y >= 18 ? m.y - 18 : m.y; // keep the label inside the canvas
      octx.fillStyle = color;
      octx.fillRect(m.x, ty, tw, 18);
      octx.fillStyle = "#000";
      octx.fillText(text, m.x + 4, ty + 2);
    }
  }

  function renderList() {
    const ul = $("det-list");
    ul.replaceChildren();
    const res = state.latest;
    $("det-empty").hidden = !!(res && res.detections.length);
    if (!res) {
      $("det-empty").textContent = "No detections yet.";
      return;
    }
    if (!res.detections.length) $("det-empty").textContent = "No objects at this confidence threshold.";
    for (const d of res.detections) {
      const li = document.createElement("li");
      li.textContent = d.label + " — " + (d.confidence * 100).toFixed(1) + "% — [" + d.bbox2d.join(", ") + "]";
      ul.appendChild(li);
    }
  }

  // ---------- camera ----------
  const camera = RT.createCameraController({
    mediaDevices: navigator.mediaDevices,
    video,
    onChange: () => refreshUI(),
    onEnded: () => {
      loop.stop();
      state.detection = "idle";
      stopVideoMeter();
      resetMeasurements();
      showMessage("The camera was disconnected or stopped by the system.");
      refreshUI();
    },
  });

  function startVideoMeter() {
    videoMeter.reset();
    if (!("requestVideoFrameCallback" in HTMLVideoElement.prototype)) return;
    const token = ++state.vfc;
    const cb = () => {
      if (token !== state.vfc) return;
      videoMeter.mark();
      video.requestVideoFrameCallback(cb);
    };
    video.requestVideoFrameCallback(cb);
  }
  function stopVideoMeter() {
    state.vfc++;
  }

  async function refreshDevices() {
    const md = navigator.mediaDevices;
    if (!md || !md.enumerateDevices) return;
    try {
      const cams = (await md.enumerateDevices()).filter((d) => d.kind === "videoinput");
      const select = $("camera-select");
      const current = select.value;
      let activeId = "";
      const stream = camera.getStream();
      if (stream && stream.getVideoTracks().length) {
        const s = stream.getVideoTracks()[0].getSettings ? stream.getVideoTracks()[0].getSettings() : {};
        activeId = s.deviceId || "";
      }
      select.replaceChildren(new Option("Default camera", ""));
      cams.forEach((d, i) => select.appendChild(new Option(d.label || "Camera " + (i + 1), d.deviceId)));
      const want = current || activeId;
      if ([...select.options].some((o) => o.value === want)) select.value = want;
    } catch (_) {
      /* the list is optional; the default camera still works */
    }
  }

  async function startCamera() {
    showMessage("");
    const r = await camera.start($("camera-select").value);
    if (!r.ok) {
      if (r.message) showMessage(r.message);
      refreshUI();
      return;
    }
    resetMeasurements();
    await refreshDevices();
    startVideoMeter();
    state.detection = "running";
    loop.start();
    refreshUI();
  }

  function stopCamera() {
    loop.stop();
    stopVideoMeter();
    camera.stop();
    state.detection = "idle";
    resetMeasurements();
    showMessage("");
    refreshUI();
  }

  function togglePause() {
    if (camera.getState() !== "on") return;
    if (state.detection === "running") {
      loop.stop();
      state.detection = "paused";
    } else {
      loop.start();
      state.detection = "running";
    }
    refreshUI();
  }

  // ---------- wiring ----------
  $("start-btn").addEventListener("click", startCamera);
  $("stop-btn").addEventListener("click", stopCamera);
  $("pause-btn").addEventListener("click", togglePause);
  $("fps-select").addEventListener("change", (e) => loop.setFps(Number(e.target.value)));
  $("conf-range").addEventListener("input", (e) => ($("conf-value").textContent = Number(e.target.value).toFixed(2)));
  $("camera-select").addEventListener("change", async () => {
    if (camera.getState() === "on") {
      stopCamera();
      await startCamera();
    }
  });
  video.addEventListener("loadedmetadata", drawOverlay);
  video.addEventListener("resize", drawOverlay);
  if ("ResizeObserver" in window) new ResizeObserver(drawOverlay).observe($("rt-stage"));
  else window.addEventListener("resize", drawOverlay);
  if (navigator.mediaDevices && navigator.mediaDevices.addEventListener) {
    navigator.mediaDevices.addEventListener("devicechange", refreshDevices);
  }

  state.timer = setInterval(refreshStats, 500);
  function cleanup() {
    loop.stop();
    stopVideoMeter();
    camera.stop(); // releases every MediaStream track
    clearInterval(state.timer);
    if (navigator.mediaDevices && navigator.mediaDevices.removeEventListener) {
      navigator.mediaDevices.removeEventListener("devicechange", refreshDevices);
    }
  }
  window.addEventListener("pagehide", cleanup);
  window.addEventListener("beforeunload", cleanup);

  refreshUI();
  refreshStats();
  loadCapabilities();
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) showMessage(RT.NO_MEDIA_MESSAGE);
})();
