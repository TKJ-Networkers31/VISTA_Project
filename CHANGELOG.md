# Changelog

Describes the documentation foundation, not application features.

## [Unreleased]
### Added (Phase 3 — object detection; sandbox-verified, X270 validation pending)
- `POST /api/v1/detection`, `GET /api/v1/detection/capabilities`, `GET /api/v1/capabilities`; `detection` in `/health`.
- Detection contract `0.3-detection`, `DetectionProvider`, YOLOX/ONNX Runtime provider, `DetectionService`.
- `ModelManager`: shared OCR + detection model residency (`VISTA_MAX_RESIDENT_MODELS` is now enforced).
- `scripts/benchmark_detection.py`, `scripts/fetch_detection_model.py`, detection tests (incl. optional real-model test).
- `docs/DETECTION.md`, ADR-0005.
### Changed
- `OCRService` optionally uses the shared `ModelManager`; `RapidOCRProvider` gained `unload()`; OCR response unchanged.
- `requirements.txt` lists `onnxruntime` and `numpy` explicitly (already installed transitively by OCR).

## [0.2.0-docs] — Phase 0
### Changed
- Rebased the foundation on the ThinkPad X270 / hybrid-inference master prompt.
- MVP narrowed to image upload + local OCR; object detection moved to Phase 3.
- Roadmap renumbered (Phases 0–10); data contracts moved to schema `0.2` with a result envelope.
- README, security, test, tech-stack, and file-tree documents rewritten accordingly.
### Added
- RESOURCE_BUDGET, WINDOWS_SETUP, CONFIGURATION, ERROR_HANDLING, OBSERVABILITY, SPATIAL_COMPUTING_PLAN, API_PROVIDER_POLICY.
- ADR-0002 (hybrid inference), ADR-0003 (spatial boundaries).
- `requirements-dev.txt`, pytest/ruff configuration, README for each planned directory.

## [0.1.0-docs] — Phase 0
Initial documentation baseline (superseded by 0.2.0-docs).

### Not implemented
No backend, OCR, detection, tracking, voice, or spatial code exists.
