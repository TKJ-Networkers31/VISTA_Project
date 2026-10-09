# Product Specification

## Functional requirements (MVP = Phases 1–5)
| ID | Requirement |
|---|---|
| FR-1 | `GET /health` reports service status and capability availability. |
| FR-2 | `POST /v1/analyze` accepts one image and returns the analysis contract ([DATA_CONTRACTS.md](DATA_CONTRACTS.md)). |
| FR-3 | OCR returns text, optional confidence, 2D bbox in original pixel coordinates. |
| FR-4 | Detection returns label, optional confidence, 2D bbox in original pixel coordinates. |
| FR-5 | Each request gets a unique `request_id`. |
| FR-6 | Validation errors return structured error responses. |
| FR-7 | Web UI uploads or captures an image and renders overlays and result lists. |
| FR-8 | `spatial` capability always reports `unavailable` in MVP. |

## Non-functional requirements
- Performance: targets are set after benchmarking; initial goal is "usable on the reference laptop" [Assumption].
- Memory: stay within 8 GB shared with OS and browser; load models lazily.
- Security/privacy: see [SECURITY_AND_PRIVACY.md](SECURITY_AND_PRIVACY.md).
- Maintainability: module boundaries per [ARCHITECTURE.md](ARCHITECTURE.md).
- Configurability: limits via environment (`.env.example`).

## User journeys
1. **Upload and read:** user opens page → selects image → sees extracted text boxes and object boxes → copies text.
2. **Bad file:** user uploads a 200 MB file → clear rejection message citing the configured limit.
3. **Partial failure:** OCR provider fails → detections still shown, OCR status `failed` with an error code.

## MVP scope
Single-image analysis, OCR, detection, responsive web UI, tests, documentation.

## Out of scope for MVP
Live camera, voice, LLM answers, tracking, depth, 3D coordinates, AR/MR/XR, user accounts, cloud deployment, model training.

## Acceptance criteria (testable)
- AC-1: Health endpoint returns HTTP 200 with JSON containing `status` and `capabilities`.
- AC-2: A fixture image with known printed text yields OCR output containing that text (match tolerance defined in tests).
- AC-3: Non-image file, oversized file, and over-pixel-limit image each return the documented error code and HTTP status.
- AC-4: All responses validate against the published JSON schema.
- AC-5: After a request, no raw image remains on disk unless retention is explicitly enabled.
- AC-6: Responses never contain spatial coordinates when `spatial.status != "available"`.
