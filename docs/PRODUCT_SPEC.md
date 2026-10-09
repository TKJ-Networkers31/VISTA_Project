# Product Specification

Labels: **[Decision]**, **[Proposal]**, **[Assumption]**, **[Open]**.

## MVP (Phases 1–2)
1. Upload an image.
2. Validate the image (type, bytes, dimensions, pixels).
3. Run OCR with a **local** provider.
4. Return extracted text, confidence when the provider supplies it, and `bbox2d`.
5. Display results in a web interface.
6. Report errors and processing status honestly.

Object detection is **not** in the MVP (moved to Phase 3; this supersedes the v0.1 draft).

## Functional requirements (MVP)
| ID | Requirement |
|---|---|
| FR-1 | `GET /health` returns service status and capability registry. |
| FR-2 | `POST /v1/analyze` accepts one image and returns the result envelope ([DATA_CONTRACTS.md](DATA_CONTRACTS.md)). |
| FR-3 | OCR items: `text`, `confidence` (nullable), `bbox2d` in original image pixels. |
| FR-4 | Every response has `schema_version`, `request_id`, `status`. |
| FR-5 | Validation and provider failures return structured errors ([ERROR_HANDLING.md](ERROR_HANDLING.md)). |
| FR-6 | Web UI uploads an image, shows status, overlay boxes, and text list. |
| FR-7 | Unsupported capabilities (detection, spatial, voice) report `not_implemented`/`unavailable`, never simulated output. |

## Non-functional requirements
Resource limits per [RESOURCE_BUDGET.md](RESOURCE_BUDGET.md); security per [SECURITY_AND_PRIVACY.md](SECURITY_AND_PRIVACY.md); no network, API key, GPU, or downloaded model required for normal test runs ([TEST_STRATEGY.md](TEST_STRATEGY.md)).

## User journeys
1. Upload image → see text boxes → copy text.
2. Upload oversized/invalid file → clear rejection citing configured limit.
3. OCR provider not installed → response status `unavailable` with explanation; no fake text.

## Later milestones (not MVP)
Detection (Phase 3), hybrid providers and image understanding (4), live camera (5), voice (6), tracking (7), spatial (8), Android/XR (9). See [ROADMAP.md](ROADMAP.md).

## Out of scope for MVP
Detection, live camera, voice, LLM, tracking, depth/pose, AR/MR/XR, accounts, cloud deployment, training.

## Acceptance criteria (testable)
- AC-1: `/health` returns 200 with `status` and `capabilities`.
- AC-2: With a mock OCR provider, `/v1/analyze` returns the documented envelope (deterministic test).
- AC-3: Invalid type, oversize bytes, over-limit pixels each return their documented error code/status.
- AC-4: Every response validates against the JSON Schema.
- AC-5: No raw image remains on disk after a request unless retention is enabled.
- AC-6: `spatial` is never populated; status is `not_implemented`.
- AC-7 (Phase 2): local OCR on a fixture returns the expected text within a defined tolerance, measured on the reference laptop.
