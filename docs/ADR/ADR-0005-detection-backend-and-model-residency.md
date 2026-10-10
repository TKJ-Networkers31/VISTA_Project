# ADR-0005: Detection backend (YOLOX via ONNX Runtime) and shared model residency

- **Status:** Proposed (awaiting owner decision). Implemented in the working tree; nothing is committed.
- **Date:** 2026-10-09 (Phase 3)

## Context
Phase 3 needs a lightweight detector for an 8 GB, CPU-only ThinkPad X270. The project license is undecided, so every
dependency and weight must be judged separately (see [../DETECTION.md](../DETECTION.md) section 2). OCR and detection
must not keep several heavy models resident by default (AI rules 11 and 17). ADR-0004 asked for the response envelope to be
decided with the owner before Phase 3; that decision has not been made.

## Decision
1. **Backend:** YOLOX-Nano (optionally Tiny), official ONNX release assets, run directly with ONNX Runtime CPU through
   `core.detection.YoloxOnnxProvider`. No new package dependency (onnxruntime, numpy and Pillow are already required).
   The model file is installed by the user (`scripts/fetch_detection_model.py`), never committed or bundled.
2. **Not adopted:** Ultralytics YOLO11n/YOLO26n (AGPL-3.0 / Enterprise license). Kept out of the dependency path.
3. **Contract:** new `DetectionResponse` (`schema_version` `0.3-detection`) in `core/contracts/detection.py`, served at
   `POST /api/v1/detection`, flat and per capability like `/api/v1/ocr`. The OCR contract is untouched.
4. **Provider abstraction:** `DetectionProvider` protocol beside `OCRProvider`; the API sees only contract objects.
5. **Residency:** one `ModelManager` shared by OCR and detection enforces `VISTA_MAX_RESIDENT_MODELS` (default 1) with
   never-unload-while-in-use, bounded waits and explicit failures. OCR gains an optional `unload()`; without a manager
   `OCRService` behaves exactly as before.
6. **Honest capabilities:** `implemented` / `status` (`available`, `unavailable`, `disabled`, `not_implemented`) /
   `model_loaded` are reported separately.

## Alternatives considered
- **Ultralytics (PyTorch/ONNX):** better accuracy per size and an easier API, but AGPL-3.0/Enterprise terms, a heavy
  PyTorch dependency for the PyTorch path, and unverified Python 3.14/Windows availability.
- **Other permissive small detectors (e.g. NanoDet, PP-YOLOE-s, RT-DETR variants):** not investigated here; license and
  export paths unverified.
- **Build the `/v1/analyze` envelope now (ADR-0004 option C):** cleaner long term, but a breaking redesign without the
  owner's decision; the flat route is additive and can later be wrapped.
- **Per-service private model state without a manager:** simplest, but cannot honor the one-heavy-model default.

## Consequences
+ No new dependencies, small model, permissive code license, fail-closed model validation, OCR behavior preserved.
- Weights license and COCO terms still need review; accuracy is modest (reported mAP 25.8 for Nano).
- Two worker pools coordinate through the manager; alternating OCR/detection with a limit of 1 reloads models.
- Memory returned to the OS after unload is not guaranteed.
- Two response styles coexist (`0.2-ocr-mvp`, `0.3-detection`) until ADR-0004 is resolved.

## Re-evaluation conditions
Project license chosen; weights/COCO review outcome; X270 measurements (latency, RSS, coexistence); need for custom
classes or higher accuracy; a second client; ADR-0004 decision; idle-eviction requirement.
