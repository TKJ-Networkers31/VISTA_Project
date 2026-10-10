# Object Detection (Phase 3)

**Status: implemented and verified in a Linux sandbox; NOT yet run on the X270 / Windows.** The backend is a YOLOX
model run directly with ONNX Runtime (CPU). The model file is not part of the repository; you install it once
(see "Model acquisition"). Until the file exists the capability reports `unavailable` and the endpoint answers 503.

## 1. What exists
| Piece | Where |
|---|---|
| Contract (`0.3-detection`) | `core/contracts/detection.py` |
| Provider interface (`DetectionProvider`, `RawDetection`) | `core/providers/base.py` |
| YOLOX/ONNX provider, letterbox/decode/NMS, label set | `core/detection/` |
| Shared model residency (OCR + detection) | `core/orchestration/model_manager.py` |
| Orchestration (admission, timeout, errors) | `core/orchestration/detection_service.py` |
| HTTP: `POST /api/v1/detection`, `GET /api/v1/detection/capabilities`, `GET /api/v1/capabilities` | `apps/api/main.py` |
| Benchmark / model fetch | `scripts/benchmark_detection.py`, `scripts/fetch_detection_model.py` |
| Tests | `tests/test_detection_contract.py`, `tests/test_detection_api.py`, `tests/test_detection_real.py` |

The route keeps the flat per-capability style of `POST /api/v1/ocr`. The unified `/v1/analyze` envelope proposed in
ADR-0004 is **not** built; see "Owner decisions".

## 2. Backend choice and licensing (verified 2026-10-09; not legal advice)
No project license is chosen yet ([LICENSE_DECISION.md](../LICENSE_DECISION.md)). This phase does not choose one.

| Component | License / terms found | Source | Status |
|---|---|---|---|
| YOLOX code | Apache-2.0 (LICENSE file read, "Copyright Megvii Inc. 2021-2022", clone at commit `6ddff48`) | github.com/Megvii-BaseDetection/YOLOX | Verified. Our decode/NMS/letterbox is an independent re-implementation of the documented algorithm; the label list matches upstream byte for byte (checked by script). Keep the Apache-2.0 notice if you ever copy upstream code. |
| YOLOX pretrained ONNX weights (`yolox_nano.onnx`, `yolox_tiny.onnx`) | **No separate weights license is stated** in the README or release notes; they are release assets of the Apache-2.0 repository, trained on COCO | release tag `0.1.1rc0` | **Needs owner / legal review** before redistribution. This repo does not redistribute them (`models/`, `*.onnx` are git-ignored). |
| COCO training data terms | Not verified (the terms page could not be read here) | cocodataset.org | **Unverified.** Review before commercial use of the weights. |
| ONNX Runtime | MIT (read from the package metadata of 1.27.0 on a third-party mirror) | PyPI / microsoft/onnxruntime | Verified from a mirror, not from PyPI directly (PyPI is unreachable from the build sandbox). |
| Ultralytics YOLO11n / YOLO26n | **AGPL-3.0, or a paid Enterprise license.** Ultralytics states all its trained models fall under AGPL-3.0 by default and that compliance means releasing the complete corresponding source of the derivative work, and lists SaaS/API use behind the model as needing the Enterprise license | ultralytics.com/license, docs.ultralytics.com/models/yolo11 and /yolo26 | **Not adopted.** Strong copyleft interacts with the still-undecided project license. |

**Why YOLOX-Nano:** permissive code license, tiny (0.91 M parameters, 1.08 GFLOPs at 416, 3.66 MB file), official ONNX
export, a documented ONNX Runtime pipeline, no PyTorch needed at runtime, same dependencies OCR already installs.
Reported COCO mAP 25.8 (upstream README), i.e. clearly weaker than larger detectors: this is a *lightweight* detector.
`yolox_tiny.onnx` (5.06 M parameters, mAP 32.8, 20.2 MB) works through the same provider; see `VISTA_DETECTION_MODEL_PATH`.

## 3. Python / platform compatibility
| Item | Evidence | Status |
|---|---|---|
| New runtime dependencies | none: `onnxruntime`, `numpy`, `Pillow` are already required by OCR (`requirements.txt` now lists the first two explicitly) | - |
| Executed here | CPython 3.13.16, Linux x86_64, onnxruntime 1.29.0, numpy 2.5.3, Pillow 12.3.0 | Verified (sandbox) |
| Python 3.11 / 3.12 + Windows wheels | `constraints/windows-cp311.txt`, `cp312.txt` (pip metadata resolution, onnxruntime 1.31.0) | Metadata only; not run on Windows |
| **Python 3.14 (your stated version)** | onnxruntime 1.27.0 metadata (third-party mirror) lists classifiers up to 3.14 and `Requires-Python >=3.11`; **but** `rapidocr-onnxruntime` 1.4.4 has `Requires-Python >=3.6,<3.13` (same mirror; the repo's own docs say the same, and that pip may silently fall back to an old 1.2.3) | **Uncertain for OCR, unverified for Windows.** Detection itself needs only onnxruntime/numpy/Pillow. |

You reported OCR passing on Python 3.14.0, which contradicts the metadata above. Please check what is installed:
```powershell
cd D:\VISTA_Project
python --version
python -m pip show rapidocr-onnxruntime onnxruntime numpy pillow
python -m pip check
# Do wheels exist for 3.14 on Windows? (resolution only, installs nothing)
python -m pip install --dry-run --only-binary=:all: --platform win_amd64 --python-version 3.14 --abi cp314 onnxruntime numpy pillow
```
I did not downgrade or change your Python. If `rapidocr-onnxruntime` shows 1.2.x you are running an older OCR than the
one the repo was validated with.

## 4. Install and model acquisition
```powershell
cd D:\VISTA_Project
python -m pip install -r requirements-dev.txt        # nothing new beyond onnxruntime/numpy (already transitive)
python -m scripts.fetch_detection_model              # downloads models\yolox_nano.onnx (3.66 MB), verifies SHA-256
Copy-Item .env.example .env -ErrorAction SilentlyContinue   # only if you have no .env; otherwise ADD the detection block
```
`fetch_detection_model` is opt-in, downloads only from the official YOLOX release URL, checks size and SHA-256 and
installs nothing on mismatch. Pinned values (computed from a download on 2026-10-09; they detect corruption, they are not
upstream-published checksums):

| Model | File | Bytes | SHA-256 |
|---|---|---|---|
| YOLOX-Nano | `yolox_nano.onnx` | 3,659,407 | `c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d` |
| YOLOX-Tiny | `yolox_tiny.onnx` | 20,219,662 | `427cc366d34e27ff7a03e2899b5e3671425c262ea2291f88bb942bc1cc70b0f7` |

Optionally pin the file at runtime with `VISTA_DETECTION_MODEL_SHA256=<hash>`; a mismatch makes the model refuse to load.
The provider also refuses a model whose input size, class count or anchor count does not match the configuration
(for example a model exported with in-graph decoding), so a wrong file fails closed instead of returning garbage.

## 5. API
`POST /api/v1/detection` multipart field `file` (JPEG/PNG/WebP, same limits as OCR, `Content-Length` required).
Optional query: `confidence` (0..1, request-level override) and `max_detections` (>=1, can only be *lower* than the
configured cap).

```powershell
curl.exe -s -F "file=@C:\path\to\photo.jpg;type=image/jpeg" "http://127.0.0.1:8000/api/v1/detection?confidence=0.4"
```
Real response (YOLOX-Nano, upstream demo image `dog.jpg` 768x576, sandbox run; `request_id` shortened; this image is
not committed):
```json
{
  "schema_version": "0.3-detection",
  "request_id": "req_f303c97904ea",
  "status": "succeeded",
  "filename": "dog.jpg",
  "image_width": 768,
  "image_height": 576,
  "coordinate_space": "image_pixels",
  "bbox_format": "xyxy",
  "detections": [
    {"class_id": 16, "label": "dog", "confidence": 0.8285, "bbox2d": [133.1, 207.0, 324.6, 542.3]},
    {"class_id": 2, "label": "car", "confidence": 0.8094, "bbox2d": [466.7, 78.2, 691.5, 171.5]},
    {"class_id": 1, "label": "bicycle", "confidence": 0.808, "bbox2d": [45.6, 131.9, 571.7, 430.6]},
    {"class_id": 15, "label": "cat", "confidence": 0.3798, "bbox2d": [131.2, 212.9, 321.6, 541.0]}
  ],
  "processing_time_ms": 154.5,
  "engine": {"id": "onnxruntime", "version": "1.29.0", "locality": "local"},
  "model": {"id": "yolox-nano", "family": "yolox", "input_size": 416, "num_classes": 80, "sha256": "c789161e…a0b7d"},
  "parameters": {"confidence_threshold": 0.3, "nms_iou_threshold": 0.45, "max_detections": 100, "input_size": 416},
  "warnings": [],
  "error": null
}
```
(`sha256` is shown shortened here; the API returns all 64 characters.) The "cat" box is a real model error: it covers
the dog. A lightweight detector makes such mistakes; the contract reports the score, it does not hide them.

Contract rules (enforced by Pydantic, so a backend bug cannot leak through):
- `bbox2d = [x_min, y_min, x_max, y_max]` in **original image pixels** (after EXIF orientation), origin top-left,
  `0 <= x_min < x_max <= image_width`, `0 <= y_min < y_max <= image_height`; coordinates are rounded to 0.1 px.
- `confidence` is finite, in `[0, 1]` (YOLOX: objectness x class probability), rounded to 4 decimals, list sorted by it.
- Empty result = `status: "succeeded"`, `detections: []`, plus a warning. Failures carry `error` and no detections.
- Invalid backend output (NaN, inverted, outside the image, unlabeled) is dropped and counted in a warning, never repaired.
- Boxes are clipped to the image; a box entirely outside is dropped. NMS is class-aware (IoU `VISTA_DETECTION_NMS_IOU`).
- The OCR response (`0.2-ocr-mvp`) is unchanged; a characterization test guards both shapes.

Errors (same envelope style, detection contract shape):
| Code | HTTP | Meaning |
|---|---|---|
| MISSING_FILE / EMPTY_FILE / CORRUPT_IMAGE | 400 | bad input |
| INVALID_PARAMETER | 400 | `confidence` / `max_detections` missing or out of range |
| LENGTH_REQUIRED | 411 | no Content-Length |
| IMAGE_TOO_LARGE / IMAGE_DIMENSIONS_EXCEEDED | 413 | bytes, side or pixel limit |
| UNSUPPORTED_FORMAT | 415 | not JPEG/PNG/WebP (verified by decoding) |
| QUEUE_FULL | 429 | bounded queue full (retryable) |
| MODEL_BUSY | 429 | another model is in use and the residency limit prevents loading this one; retryable |
| DETECTION_DISABLED / DETECTOR_UNAVAILABLE / DETECTOR_LOAD_FAILED | 503 | status `unavailable` |
| DETECTOR_FAILED / MODEL_UNLOAD_FAILED / INTERNAL_ERROR | 500 | no internal text is exposed |
| TASK_TIMEOUT | 504 | `VISTA_TASK_TIMEOUT_SECONDS` exceeded; the running model call cannot be interrupted |
| CANCELLED / SERVER_SHUTTING_DOWN | 503 | stopped before inference / shutdown |

### Capabilities
`GET /api/v1/capabilities` (all), `GET /api/v1/detection/capabilities`, and `detection` inside `GET /health`.
| Field | Meaning |
|---|---|
| `implemented` | code exists (`true` for detection; `spatial` is `false`) |
| `status` | `available` = libraries importable, model file present, last load did not fail; `unavailable` = missing file/package or last load failed; `disabled` = `VISTA_DETECTION_ENABLED=false`; `not_implemented` = no code (`spatial`) |
| `model_loaded` | the model is in RAM right now (`available` does not imply this) |

`available` is a readiness claim, not proof of inference: only a real request (or the real-backend test) proves that.
The existing `GET /api/v1/ocr/capabilities` is unchanged (no `detection` key).

## 6. Configuration reference
All variables are optional; invalid values stop startup with a message naming the variable (never its value).
| Variable | Default | Notes |
|---|---|---|
| `VISTA_DETECTION_ENABLED` | `true` | `false` -> `disabled`, endpoint answers 503 `DETECTION_DISABLED` |
| `VISTA_DETECTION_BACKEND` | `yolox-onnx` | only supported value |
| `VISTA_DETECTION_MODEL_PATH` | `models/yolox_nano.onnx` | relative paths resolve against the repository root; no machine-specific default |
| `VISTA_DETECTION_MODEL_ID` | `yolox-nano` | label echoed in responses; set it truthfully when you switch files |
| `VISTA_DETECTION_MODEL_SHA256` | empty | optional 64-hex pin; mismatch refuses to load |
| `VISTA_DETECTION_INPUT_SIZE` | `416` | must equal the model's fixed size (multiple of 32, <= 2048); nano and tiny are 416 |
| `VISTA_DETECTION_CONF_THRESHOLD` | `0.30` | 0..1 |
| `VISTA_DETECTION_NMS_IOU` | `0.45` | 0..1 |
| `VISTA_DETECTION_MAX_DETECTIONS` | `100` | >= 1 |
| `VISTA_DETECTION_THREADS` | `0` | 0 = ONNX Runtime decides; set e.g. `2` to leave CPU for the browser/IDE |
| `VISTA_MAX_RESIDENT_MODELS` | `1` | heavy models in RAM at once across OCR + detection (now actually enforced) |
| `VISTA_MODEL_ACQUIRE_TIMEOUT_SECONDS` | `30` | wait for another model to become idle before `MODEL_BUSY` |
Upload limits, queue size, worker count and task timeout are the existing OCR settings and apply to detection too.

## 7. OCR + detection on 8 GB: what is and is not guaranteed
`ModelManager` (one instance, shared by both services) enforces, and tests cover:
- at most `VISTA_MAX_RESIDENT_MODELS` models are loaded **as far as this manager knows**; default 1;
- a model is loaded only inside `use()`, serialized per model (no duplicate loads under concurrency);
- a model with an active user is never unloaded; making room unloads only **idle** models;
- a waiter gives up after `VISTA_MODEL_ACQUIRE_TIMEOUT_SECONDS` (`MODEL_BUSY`), is woken when a model is released, and
  stops on request cancellation or shutdown; there are no unbounded waits;
- a failed unload is an error (`MODEL_UNLOAD_FAILED`), the cap is not silently exceeded.

Limitations (not hidden):
- **Memory reclamation is not guaranteed.** "Unload" drops Python references and runs `gc.collect()`. ONNX Runtime and the
  allocator may keep memory in the process, so RSS may not fall back to its earlier level. Not measured on the X270.
- With the default 1, alternating OCR and detection requests **reload models each time** (OCR load was ~0.3 s on Linux,
  but ~10 s on a first ever load; detection nano loads in tens of ms). Set 2 if RAM allows after measuring.
- Both services have their own worker pool and queue, so a request can wait in a worker for the other model (up to the
  acquire timeout). `use()` is not re-entrant (nothing holds two models).
- Idle-timeout unloading (`VISTA_MODEL_IDLE_UNLOAD_SECONDS`) is **not implemented** (it was not before either).
- Python libraries imported by a model (onnxruntime itself) stay resident; only the model object is released.
- A task already inside `session.run` cannot be interrupted; timeouts free the HTTP request, the slot frees later.
Smallest follow-up if needed: an idle-eviction timer in `ModelManager`, plus a `psutil`-based free-RAM floor check.

## 8. Tests
```powershell
cd D:\VISTA_Project
python -m pytest -q                                        # everything that needs no model (OCR + detection, fakes)
python -m pytest -q tests/test_ocr_api.py tests/test_validation_prep.py       # OCR regression only
python -m pytest -q tests/test_detection_contract.py tests/test_detection_api.py   # detection contract + API + lifecycle
python -m pytest -q -m requires_model -s tests/test_real_engine.py            # REAL OCR (existing)
python -m scripts.fetch_detection_model                                       # once
python -m pytest -q -m requires_model -s tests/test_detection_real.py         # REAL detection
```
Expected, for the default run: all tests pass, none need a model or network (the build sandbox saw `138 passed,
18 deselected` with fake providers; that number is a sandbox result, yours may differ if you add tests).
Fake-provider tests prove plumbing, **not** that detection works. The real-backend test fails (not skips) if the
model file is missing, like the OCR real tests. To check real objects with your own photo (none is committed):
```powershell
$env:VISTA_DETECTION_TEST_IMAGE = "C:\path\photo.jpg"; $env:VISTA_DETECTION_TEST_EXPECT = "person,car"
python -m pytest -q -m requires_model -s tests/test_detection_real.py -k user_image
```

## 9. Benchmark
```powershell
python -m scripts.benchmark_detection --runs 20 --warmup 3 --label "X270 AC power, browser closed"
python -m scripts.benchmark_detection --images C:\path\to\my_photos --label "X270 own photos"
```
Writes `results\benchmark-detection-*.json` (git-ignored) and prints a summary. **Send back the printed summary and the
JSON.** It records: Python and package versions, CPU/RAM, backend/model id/SHA-256, device (`CPUExecutionProvider`),
model init time, first (cold) inference, warm median and p95 per image size, per-stage medians (preprocess / ONNX
inference / postprocess), detection counts, process RSS before and after load, before and after inference and its peak
during inference, and failed runs.

How to read it:
- RSS is the **whole process** (interpreter, libraries, model, buffers). `after load - before load` is a rough
  indication of model cost, not an exact incremental figure; the OS may retain freed memory.
- p95 over few samples is close to the maximum; use `--runs` of 20+ and look at `n`.
- Default inputs are deterministic synthetic images (fixed seed): latency is meaningful, **detection counts are not**
  (no real objects). Use `--images` for realistic counts.
- Provider-level timings exclude HTTP, upload parsing and image decoding; end-to-end latency is higher (see
  `processing_time_ms` in a real API response, which includes decoding).
- Large images are dominated by preprocessing (PIL resize), not the network: the network input is always 416x416.
Sandbox figures are in [RESOURCE_BUDGET.md](RESOURCE_BUDGET.md) and are labeled as such. **No X270 figure exists yet.**

## 10. Candidate evaluation: Ultralytics YOLO11n / YOLO26n
Not evaluated here, deliberately:
1. License: AGPL-3.0 or paid Enterprise (section 2); adoption is a project-license decision for the owner.
2. Runtime path: I could not verify the `ultralytics` package on Python 3.14/Windows (PyPI is unreachable from the
   build sandbox), and the raw ONNX output layout of YOLO26 (reported NMS-free) was not verified, so a standalone
   ONNX Runtime comparison cannot be written reliably. Running an ONNX file through the Ultralytics wrapper and calling it
   an ONNX Runtime benchmark would be misleading, so no script was added.
3. Reported (not measured by us) CPU-ONNX figures on a Xeon, from Ultralytics docs: YOLO11n 56.1 ms, YOLO26n 38.9 ms at
   640 px, 2.6 M / 2.4 M parameters. They are not comparable to our 416 px YOLOX numbers or to the X270.
If the owner accepts AGPL/Enterprise terms, evaluate in a **separate virtual environment** (never in the production
dependency path): export each model to ONNX, run PyTorch and ONNX Runtime as separate backends, same images, same
`scripts.benchmark_detection` methodology, record versions and licenses.

## 11. Known issues and unsupported features
- Only COCO's 80 classes; no custom classes, tracking, segmentation, pose or depth (`spatial` is `not_implemented`).
- Accuracy is that of YOLOX-Nano and was **not measured** here beyond sanity checks on two upstream demo images.
  Expect misses and false positives (see the "cat" box above). Preprocessing uses PIL bilinear resize while upstream
  uses OpenCV `INTER_LINEAR`; the effect on accuracy is unmeasured.
- Class-aware NMS is used (reference demo is class-agnostic), so overlapping boxes of different classes can both appear.
- Batch inference, GPU/DirectML providers and dynamic input sizes are not supported.
- First request after start loads the model (tens of ms to seconds, depends on disk cache).
- `ruff` and Windows were not run in the build sandbox; only a manual line-length/syntax/unused-import check was.
- Real OCR was not re-run in the sandbox (`rapidocr-onnxruntime` is not installed there); OCR regression there covers
  the existing 45 mock-engine tests, unchanged and passing. Run `pytest -m requires_model tests/test_real_engine.py` locally.

## 12. Remaining owner decisions
1. Project license (still open; affects how the weights/AGPL question is judged).
2. Review of the YOLOX pretrained-weights and COCO terms before any redistribution or commercial use.
3. Contract envelope: keep per-capability routes, or build the ADR-0004 `/v1/analyze` envelope now that two capabilities exist.
4. Accept or change ADR-0005 (backend and shared residency).
5. Whether to implement idle-timeout unloading and a free-RAM floor (needs X270 measurements).
