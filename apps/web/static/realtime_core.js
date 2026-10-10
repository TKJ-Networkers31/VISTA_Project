"use strict";
/* Pure logic for the Realtime Detection page: no DOM access, so it runs in the browser (global VistaRT)
   and in Node (module.exports) for unit tests. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.VistaRT = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const NO_MEDIA_MESSAGE =
    "The camera API is unavailable. Open this page via http://127.0.0.1:8000 or HTTPS " +
    "(browsers only allow camera access in a secure context).";

  class RTError extends Error {
    constructor(kind, message, extra) {
      super(message);
      const e = extra || {};
      this.name = "RTError";
      this.kind = kind; // capture | timeout | network | http | invalid
      this.status = e.status == null ? null : e.status;
      this.code = e.code || null;
    }
  }

  const isNum = (v) => typeof v === "number" && Number.isFinite(v);

  // ---------- geometry ----------
  /** Where an srcW x srcH picture lands inside a boxW x boxH container with object-fit: contain. */
  function containRect(srcW, srcH, boxW, boxH) {
    if (![srcW, srcH, boxW, boxH].every((v) => isNum(v) && v > 0)) return null;
    const scale = Math.min(boxW / srcW, boxH / srcH);
    const width = srcW * scale;
    const height = srcH * scale;
    return { x: (boxW - width) / 2, y: (boxH - height) / 2, width, height, scale };
  }

  /** bbox2d (xyxy, in an imgW x imgH image) -> {x, y, w, h} in container pixels. null if invalid. */
  function mapBox(bbox, imgW, imgH, rect) {
    if (!rect || !(imgW > 0) || !(imgH > 0)) return null;
    if (!Array.isArray(bbox) || bbox.length !== 4 || !bbox.every(isNum)) return null;
    const [x1, y1, x2, y2] = bbox;
    if (x2 <= x1 || y2 <= y1) return null;
    const sx = rect.width / imgW;
    const sy = rect.height / imgH;
    return { x: rect.x + x1 * sx, y: rect.y + y1 * sy, w: (x2 - x1) * sx, h: (y2 - y1) * sy };
  }

  /** Size of the frame sent to the backend: same aspect ratio, longest side <= maxSide, never upscaled. */
  function captureSize(vw, vh, maxSide) {
    if (![vw, vh, maxSide].every((v) => isNum(v) && v > 0)) return null;
    const k = Math.min(1, maxSide / Math.max(vw, vh));
    return { width: Math.max(1, Math.round(vw * k)), height: Math.max(1, Math.round(vh * k)) };
  }

  // ---------- response / error handling ----------
  /** Strict check of a succeeded 0.3-detection body before anything is drawn. */
  function validateResponse(b) {
    const bad = (reason) => ({ ok: false, reason });
    if (!b || typeof b !== "object") return bad("the response is not a JSON object");
    if (b.status !== "succeeded") return bad("unexpected status " + String(b.status));
    if (!(Number.isInteger(b.image_width) && b.image_width > 0 && Number.isInteger(b.image_height) && b.image_height > 0))
      return bad("missing or invalid image size");
    if (!Array.isArray(b.detections)) return bad("detections is not a list");
    for (const d of b.detections) {
      if (!d || typeof d.label !== "string" || !isNum(d.confidence) || d.confidence < 0 || d.confidence > 1)
        return bad("invalid detection entry");
      const x = d.bbox2d;
      if (!Array.isArray(x) || x.length !== 4 || !x.every(isNum)) return bad("invalid bbox2d");
      if (x[2] <= x[0] || x[3] <= x[1] || x[0] < 0 || x[1] < 0 || x[2] > b.image_width || x[3] > b.image_height)
        return bad("bbox2d outside the reported image");
    }
    return { ok: true };
  }

  function describeCameraError(err) {
    const name = err && err.name;
    switch (name) {
      case "NotAllowedError":
      case "SecurityError":
        return "Camera permission was denied. Allow camera access for this site in the browser, then press Start camera again.";
      case "NotFoundError":
      case "DevicesNotFoundError":
        return "No camera was found. Connect a webcam and try again.";
      case "NotReadableError":
      case "TrackStartError":
      case "AbortError":
        return "The camera could not be started. It may be in use by another application.";
      case "OverconstrainedError":
        return "The selected camera is not available. Choose another camera or the default one.";
      default:
        return "Could not start the camera" + (name ? " (" + name + ")" : "") + ".";
    }
  }

  const BACKEND_BY_CODE = {
    DETECTOR_UNAVAILABLE: "The detection model is not ready (model file or packages missing). See docs/DETECTION.md.",
    DETECTOR_LOAD_FAILED: "The detection model could not be loaded. Check the server log.",
    DETECTION_DISABLED: "Detection is disabled on the server (VISTA_DETECTION_ENABLED=false).",
    QUEUE_FULL: "The server is busy; frames are being retried more slowly.",
    MODEL_BUSY: "Another model (OCR) is using the memory slot; retrying shortly.",
    TASK_TIMEOUT: "The server did not finish a frame in time; retrying more slowly.",
    DETECTOR_FAILED: "The detection backend failed on a frame.",
    SERVER_SHUTTING_DOWN: "The server is shutting down.",
  };

  /** -> {message}. Only describes; the loop keeps running and backs off by itself. */
  function describeBackendError(err) {
    if (!err) return { message: "Unknown error." };
    switch (err.kind) {
      case "timeout":
        return { message: "The server did not answer in time. Detection will keep retrying." };
      case "network":
        return { message: "Cannot reach the VISTA server. Is it still running?" };
      case "invalid":
        return { message: "The server sent an unexpected response (" + err.message + ")." };
      case "capture":
        return { message: "Could not capture a camera frame: " + err.message };
      case "http":
        return { message: BACKEND_BY_CODE[err.code] || (err.message || "HTTP " + err.status) };
      default:
        return { message: err.message || "Unexpected error." };
    }
  }

  // ---------- statistics ----------
  function median(values) {
    if (!values.length) return null;
    const s = values.slice().sort((a, b) => a - b);
    const m = s.length >> 1;
    return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
  }

  /** Events per second over a sliding window. Returns null when there are fewer than 2 recent events. */
  function createRateMeter(windowMs, now) {
    const clock = now || (() => Date.now());
    let marks = [];
    const prune = () => {
      const limit = clock() - windowMs;
      marks = marks.filter((t) => t >= limit);
    };
    return {
      mark() {
        marks.push(clock());
        prune();
      },
      rate() {
        prune();
        if (marks.length < 2) return null;
        const span = marks[marks.length - 1] - marks[0];
        return span > 0 ? ((marks.length - 1) * 1000) / span : null;
      },
      reset() {
        marks = [];
      },
    };
  }

  // ---------- single-flight detection loop ----------
  const clampFps = (v) => (isNum(v) ? Math.min(10, Math.max(0.5, v)) : 2);

  /**
   * Sends at most ONE frame at a time. The next frame is scheduled only after the previous request settled,
   * spaced to the target FPS; consecutive errors add a bounded backoff but never end the loop.
   * stop() aborts the in-flight request and marks its result stale; start() after stop() cannot overlap it.
   */
  function createDetectionLoop(o) {
    const now = o.now || (() => Date.now());
    const setT = o.setTimer || ((f, ms) => setTimeout(f, ms));
    const clearT = o.clearTimer || ((id) => clearTimeout(id));
    const mkCtl = o.makeController || (() => new AbortController());
    let fps = clampFps(o.fps);
    let active = false;
    let inFlight = false;
    let timer = null;
    let gen = 0;
    let ctl = null;
    let errors = 0;
    const stats = { sent: 0, ok: 0, failed: 0, skipped: 0, stale: 0 };

    function schedule(delay) {
      if (timer !== null) clearT(timer);
      timer = setT(tick, delay);
    }

    function nextDelay(t0) {
      const base = Math.max(0, 1000 / fps - (now() - t0));
      const backoff = errors > 0 ? Math.min(5000, 250 * Math.pow(2, errors - 1)) : 0;
      return base + backoff;
    }

    function tick() {
      timer = null;
      if (!active || inFlight) return; // an in-flight request reschedules itself when it settles
      run();
    }

    async function run() {
      const myGen = gen;
      const t0 = now();
      const c = mkCtl();
      inFlight = true;
      ctl = c;
      try {
        const frame = await o.capture();
        if (myGen !== gen || !active) {
          stats.stale++;
        } else if (frame == null) {
          stats.skipped++; // video not ready yet
        } else {
          stats.sent++;
          const result = await o.send(frame, c.signal);
          if (myGen !== gen || !active) {
            stats.stale++;
          } else {
            errors = 0;
            stats.ok++;
            o.onResult(result, { roundTripMs: now() - t0 });
          }
        }
      } catch (err) {
        if (myGen !== gen || !active) {
          stats.stale++;
        } else {
          errors++;
          stats.failed++;
          try {
            o.onError(err, { consecutiveErrors: errors });
          } catch (_) {
            /* a faulty callback must not stop the loop */
          }
        }
      } finally {
        inFlight = false;
        if (ctl === c) ctl = null;
        if (active) schedule(nextDelay(t0));
      }
    }

    return {
      start() {
        if (active) return;
        active = true;
        gen++;
        errors = 0;
        schedule(0);
      },
      stop() {
        if (!active) return;
        active = false;
        gen++;
        if (timer !== null) {
          clearT(timer);
          timer = null;
        }
        if (ctl) ctl.abort();
      },
      setFps(v) {
        fps = clampFps(v);
      },
      isActive: () => active,
      isBusy: () => inFlight,
      stats: () => Object.assign({}, stats),
    };
  }

  // ---------- camera lifecycle ----------
  /** Owns the MediaStream: start, stop (all tracks), cancel-while-starting, device-unplugged. */
  function createCameraController(o) {
    let state = "off"; // off | starting | on | error
    let stream = null;
    let token = 0;
    const emit = () => o.onChange && o.onChange(state);

    function stopTracks(s) {
      s.getTracks().forEach((t) => {
        if (t.removeEventListener) t.removeEventListener("ended", onEnded);
        t.stop();
      });
    }

    function onEnded() {
      if (state !== "on") return;
      stop();
      if (o.onEnded) o.onEnded();
    }

    async function start(deviceId) {
      if (state === "starting" || state === "on") return { ok: false, reason: "busy" };
      const md = o.mediaDevices;
      if (!md || typeof md.getUserMedia !== "function") {
        state = "error";
        emit();
        return { ok: false, message: NO_MEDIA_MESSAGE };
      }
      const my = ++token;
      state = "starting";
      emit();
      const video = { width: { ideal: 1280 }, height: { ideal: 720 } };
      if (deviceId) video.deviceId = { exact: deviceId };
      let s;
      try {
        s = await md.getUserMedia({ audio: false, video });
      } catch (err) {
        if (my !== token) return { ok: false, reason: "cancelled" };
        state = "error";
        emit();
        return { ok: false, message: describeCameraError(err), name: err && err.name };
      }
      if (my !== token) {
        stopTracks(s); // stop() was called while the permission prompt was open
        return { ok: false, reason: "cancelled" };
      }
      stream = s;
      o.video.srcObject = s;
      s.getVideoTracks().forEach((t) => t.addEventListener("ended", onEnded));
      try {
        if (o.video.play) await o.video.play();
      } catch (_) {
        /* autoplay refusal: the stream is still attached and the user can interact */
      }
      if (my !== token) return { ok: false, reason: "cancelled" };
      state = "on";
      emit();
      return { ok: true };
    }

    function stop() {
      token++;
      if (stream) {
        stopTracks(stream);
        stream = null;
      }
      o.video.srcObject = null;
      state = "off";
      emit();
    }

    return { start, stop, getState: () => state, getStream: () => stream };
  }

  return {
    NO_MEDIA_MESSAGE, RTError, containRect, mapBox, captureSize, validateResponse, describeCameraError,
    describeBackendError, median, createRateMeter, createDetectionLoop, createCameraController,
  };
});
