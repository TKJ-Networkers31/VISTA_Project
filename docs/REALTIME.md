# Realtime Detection (Phase 3.1)

**Status: implemented; logic unit-tested in Node with fakes; NOT yet run in a real browser, with a real webcam, on Windows or on the X270.** Follow the manual procedure in section 6 before treating it as working.

## 1. What it is
A browser page (`/static/realtime.html`) that shows the webcam preview and draws boxes from the **existing** image endpoint `POST /api/v1/detection` (schema `0.3-detection`). No new backend endpoint, WebSocket or video stream exists; the backend is unchanged.

| Piece | Path |
|---|---|
| Page / styles | `apps/web/static/realtime.html`, `realtime.css` |
| DOM glue (camera buttons, capture, fetch, overlay, stats) | `apps/web/static/realtime.js` |
| Pure logic (single-flight loop, camera controller, geometry, validation, meters) | `apps/web/static/realtime_core.js` |
| Tests | `tests/js/realtime_core.test.js` (Node), `tests/test_realtime_ui.py` (pytest) |

The frontend is plain HTML/CSS/JS served by FastAPI (`/static`). There is no build step and no new dependency.

## 2. Run it (Windows, PowerShell)
```powershell
cd D:\VISTA_Project
.\.venv\Scripts\Activate.ps1
python -m scripts.fetch_detection_model        # once, if models\yolox_nano.onnx is missing
python -m apps.api                             # backend + UI on http://127.0.0.1:8000
```
Open **http://127.0.0.1:8000/static/realtime.html** (also linked from the OCR page). Press **Start camera** and allow access.

**Secure context:** browsers expose the camera only on `localhost`/`127.0.0.1` or HTTPS. Opening the page through a LAN IP (for example from a phone) over plain HTTP will not work and the page says so. LAN exposure is a separate, deliberate step (see SECURITY_AND_PRIVACY.md); this feature does not add it.

## 3. Using it
- **Start camera / Stop camera:** Stop releases every MediaStream track (the camera light goes off). The camera never starts by itself.
- **Pause / Resume detection:** the preview keeps running; only frame uploads stop/start.
- **Camera:** list from `enumerateDevices()`; names appear after the first permission grant. Changing it while the camera is on restarts the stream.
- **Target detection FPS** (1, 2, 3, 5; default 2): an upper bound for how often a frame is sent.
- **Frame size sent** (416 or 640 px longest side): the frame is resized in the browser (aspect ratio kept, never upscaled) and sent as JPEG quality 0.7. The model input is 416 px, so 416 is cheapest; 640 costs more upload/decoding for little benefit with YOLOX-Nano.
- **Confidence threshold:** sent as the `confidence` query parameter of the existing endpoint (applies to the next frame).

## 4. What the numbers mean
| Value | Meaning |
|---|---|
| Video FPS | frames the browser actually painted in the preview (`requestVideoFrameCallback`, 3 s window). `n/a (unsupported)` if the browser lacks that API. |
| Detection FPS | completed, accepted detection responses per second (5 s window). Limited by the target FPS **and** by backend speed. |
| Round trip (median of last 20) | from the start of frame capture to the parsed response: capture + JPEG encode + upload + server queue + decode + inference + response. |
| Server processing | `processing_time_ms` from the response (server-side decode + inference + normalization). |
| Failed requests | timeouts, network errors, non-2xx and invalid responses since the camera started. |

All values are measured in the current session; `n/a` means nothing measured yet. Nothing is estimated.

## 5. Design and safety
- **Single-flight:** at most one frame request is in flight. The next one is scheduled only after the previous one settled, spaced to the target FPS. If the backend is slower than the target, detection FPS drops; requests never pile up.
- **Stale results:** pause, stop and camera change bump a generation counter and abort the in-flight request; a late result from an earlier generation is dropped, never drawn. Rapid pause/resume cannot start a second loop.
- **Errors do not stop the preview or the loop:** timeouts (8 s per request), network loss, 429/503/500 and invalid bodies show a message and add a bounded backoff (250 ms doubling, max 5 s) between attempts. After 3 consecutive failures the old boxes are cleared and the capability status is re-read. The loop recovers by itself when the backend does.
- **Backend rules untouched:** requests go through `DetectionService`, so the bounded queue, `ModelManager`, timeout/cancellation, upload limits and validation apply as for image uploads. `QUEUE_FULL` and `MODEL_BUSY` (429) are handled as retryable.
- **Boxes come from the response:** `bbox2d` (xyxy, pixels of the *sent* frame) is scaled with `image_width/image_height` from the response into the video's `object-fit: contain` area, so letterboxing/pillarboxing and container resizes do not shift boxes. The overlay is redrawn on resize.
- **Privacy:** frames exist only in memory (canvas → JPEG blob → request). The page does not store them (no localStorage/IndexedDB), the server does not retain them (`VISTA_RETAIN_RAW_IMAGES=false`; covered by a test), and the page contacts only the VISTA server that served it.
- **Rendering of server text uses `textContent`** only (no `innerHTML`).

## 6. Tests
Automated (no webcam, no model, no network):
```powershell
python -m pytest -q                                 # includes tests/test_realtime_ui.py
node --test tests/js/realtime_core.test.js          # Node 18+; no npm packages
python -m ruff check .
```
Node tests cover: coordinate mapping for several aspect ratios and container sizes, capture sizing, response validation, error texts, rate meter, the single-flight loop (pacing, no overlap with a slow backend, stale results after stop, rapid pause/resume, error backoff/recovery, skipped frames, faulty callbacks), and the camera controller (start/stop releasing all tracks, permission denied / not found / not readable, insecure context, stop during the permission prompt, double start, device unplugged, restart without leaks) using fake MediaDevices.

**Not automated (do this on the X270, record results):**
- [ ] R-1 Open `http://127.0.0.1:8000/static/realtime.html`; status pills show Backend: ready.
- [ ] R-2 Start camera → allow → preview is continuous; “Camera: on · detecting”.
- [ ] R-3 Hold up a person/cup/phone: boxes and labels sit on the object; resize the window and toggle fullscreen: boxes stay aligned.
- [ ] R-4 Compare Video FPS vs Detection FPS at target 1/2/3/5 and frame size 416/640; note median round trip. Record CPU model, power mode, browser and Python version next to the numbers.
- [ ] R-5 Pause → boxes stop updating, preview continues, Detection FPS decays to n/a; Resume → updates again; click Pause/Resume rapidly 10 times; check Task Manager/`netstat` shows no growing request backlog.
- [ ] R-6 Stop camera → camera LED off, overlay cleared. Reload the page while on → LED off.
- [ ] R-7 Deny the permission (or block camera in site settings) → clear message, preview not shown.
- [ ] R-8 Close other apps using the camera (Teams/Zoom) → start while it is busy → “in use” message.
- [ ] R-9 Stop the Python server while running → error message and preview keeps running; start the server again → recovers without reloading the page.
- [ ] R-10 Rename `models\yolox_nano.onnx` temporarily → page shows the model-not-ready message (503); restore it.
- [ ] R-11 Run an OCR upload at `/` while realtime is detecting with `VISTA_MAX_RESIDENT_MODELS=1` → either works after a model swap or shows MODEL_BUSY, then recovers. Note how long swaps take.
- [ ] R-12 Unplug a USB webcam while running → “disconnected” message, camera state off.
- [ ] R-13 Leave it running 10+ minutes; watch `python.exe` RAM and the browser tab memory for growth.

## 7. Known limitations
- Not measured anywhere yet: real FPS, latency and memory on the X270. The 397 ms single request reported earlier is one image request, not a FPS benchmark.
- With `VISTA_MAX_RESIDENT_MODELS=1` (default), alternating OCR and detection reloads models; using OCR while realtime runs can cause `MODEL_BUSY` for a moment.
- A request already inside ONNX Runtime cannot be interrupted; after Stop its slot frees when the model call ends.
- Detections are independent per frame: no tracking, no ids, boxes can flicker. Only COCO classes; YOLOX-Nano makes mistakes (see DETECTION.md).
- The frame shown in the preview is slightly newer than the frame the boxes belong to (round-trip delay); fast motion shows the lag.
- Browsers may throttle timers and video callbacks in background tabs; keep the tab visible.
- `requestVideoFrameCallback` is not available in all browsers; Video FPS then shows `n/a`.
- Only the first camera stream is handled; no mirroring, no recording, no snapshot saving.

## 8. Troubleshooting
| Symptom | Likely cause / action |
|---|---|
| “The camera API is unavailable…” | Page opened over plain HTTP on a non-localhost address. Use `http://127.0.0.1:8000` or HTTPS. |
| “Camera permission was denied” | Allow the camera in the address-bar site settings, then Start camera again. Windows: Settings → Privacy → Camera must allow desktop/browser apps. |
| “No camera was found” | Webcam disconnected or disabled; check Device Manager. |
| “…in use by another application” | Close Teams/Zoom/Camera app, or pick another camera. |
| Backend: unavailable / 503 `DETECTOR_UNAVAILABLE` | Model file missing: `python -m scripts.fetch_detection_model`; see DETECTION.md. |
| 503 `DETECTION_DISABLED` | `VISTA_DETECTION_ENABLED=false` in `.env`. |
| 504 / “did not answer in time” | CPU too slow for the settings: lower target FPS, use 416 px, close other apps; or raise `VISTA_TASK_TIMEOUT_SECONDS`. |
| 429 `QUEUE_FULL` / `MODEL_BUSY` | Backend busy (or OCR holds the memory slot); the page retries with backoff. |
| Boxes look offset | Hard-reload (Ctrl+F5) to drop cached JS, and report the browser, window size and the camera resolution. |

## Paste-in updates for existing docs
- **README.md** (capability table): add `Realtime camera detection (browser, existing detection API) | Implemented in Phase 3.1; logic tested with fakes; browser/webcam/Windows validation pending (docs/REALTIME.md)`; add `[Realtime](docs/REALTIME.md)` to the documentation index.
- **CHANGELOG.md** `[Unreleased]` → Added: `Realtime Detection page (apps/web/static/realtime.*), single-flight frame loop, camera controller, Node unit tests, tests/test_realtime_ui.py, docs/REALTIME.md. Backend unchanged.`
- **docs/FILE_TREE.md**: under `apps/web`: `static/realtime.html, realtime.css, realtime.js, realtime_core.js`; under `tests`: `js/realtime_core.test.js, test_realtime_ui.py`.
- **docs/ROADMAP.md** Phase 3 note: realtime preview delivered as 3.1; Phase 5 (live camera with bounded frame queue/drop-oldest/soak test) is still open and not started.
