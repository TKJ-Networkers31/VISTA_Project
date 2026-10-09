# Roadmap

Time estimates are intentionally omitted; any future estimate must be marked as a preliminary guess. Each phase must meet its exit condition before the next starts.

## Phase 0: Planning and repository foundation

- **Goal:** Documentation baseline and repo hygiene.
- **Features:** Docs, AI rules, root files.
- **Dependencies:** None.
- **Output:** This documentation set.
- **Acceptance criteria:** All docs exist, links resolve, Mermaid and JSON validated, owner reviews open questions.
- **Risks:** Scope drift; docs inconsistent.
- **Condition to proceed:** Owner accepts v0.1 and records decisions in the decision log.

## Phase 1: Backend skeleton and health endpoint

- **Goal:** Minimal FastAPI app bootstrap (not OCR/vision).
- **Features:** `GET /health`, config loading, error format, logging without image data.
- **Dependencies:** Phase 0; verified Python/FastAPI versions.
- **Output:** Runnable app, pinned dependencies, first tests.
- **Acceptance criteria:** Health returns 200; config limits load from env; tests pass in a real run.
- **Risks:** Dependency incompatibility on Windows.
- **Condition to proceed:** Tests pass; dependency versions recorded.

## Phase 2: Image intake and OCR

- **Goal:** Safe upload, decoding, OCR provider behind interface.
- **Features:** `POST /v1/analyze` with OCR; validation limits.
- **Dependencies:** Phase 1; OCR engine verified to install and run on target hardware.
- **Output:** OCR results in the data contract.
- **Acceptance criteria:** Fixture text recovered; invalid inputs rejected; memory measured.
- **Risks:** OCR install size/RAM too high; accuracy on real photos.
- **Condition to proceed:** Measured latency and RAM acceptable to owner, or alternative engine chosen via ADR.

## Phase 3: Object detection

- **Goal:** Detector behind interface, normalized output.
- **Features:** Detection in the same response.
- **Dependencies:** Phase 2; detector model and license verified.
- **Output:** Detection results, partial-failure handling.
- **Acceptance criteria:** Boxes map to original pixels; contract tests pass.
- **Risks:** CPU latency; model license.
- **Condition to proceed:** Latency measured; license confirmed.

## Phase 4: Responsive web interface

- **Goal:** Browser UI for upload and overlays.
- **Features:** Upload/capture, canvas overlay, result lists, error display.
- **Dependencies:** Phases 2–3 API stable.
- **Output:** `apps/web` static UI.
- **Acceptance criteria:** Works on laptop and Android browser; overlay boxes align.
- **Risks:** Mobile layout, coordinate scaling bugs.
- **Condition to proceed:** Manual and UI tests pass on both clients.

## Phase 5: Integration, security, testing, MVP release

- **Goal:** Hardening and release.
- **Features:** Limits, temp-file cleanup, schema validation, docs sync.
- **Dependencies:** Phases 1–4.
- **Output:** MVP tag, honest status in README.
- **Acceptance criteria:** All acceptance criteria in PRODUCT_SPEC pass; security checklist complete.
- **Risks:** Hidden resource exhaustion paths.
- **Condition to proceed:** Owner signs off MVP.

## Phase 6: Live camera prototype

- **Goal:** Near-real-time analysis from camera.
- **Features:** Frame capture, bounded queue, overlay, tracking basics.
- **Dependencies:** MVP; measured per-frame cost.
- **Output:** Live prototype.
- **Acceptance criteria:** Stable under load with dropped frames, no unbounded memory growth.
- **Risks:** CPU too slow on i7-7th gen; browser camera permissions over HTTP.
- **Condition to proceed:** Measured frame rate acceptable; HTTPS/local-network approach decided.

## Phase 7: Voice and contextual AI

- **Goal:** Voice question answered from visual context.
- **Features:** STT, target association, LLM provider, TTS/text.
- **Dependencies:** Phase 6 scene state; LLM/STT provider choice (open).
- **Output:** Voice flow independent of vision loop.
- **Acceptance criteria:** Vision loop latency unchanged while LLM runs; answers grounded in evidence.
- **Risks:** Cost, privacy of cloud providers, hallucination.
- **Condition to proceed:** Provider decision recorded in ADR.

## Phase 8: Spatial tracking and coordinate systems

- **Goal:** Coordinate transforms with real pose/depth.
- **Features:** Camera-space vs world-space model, transforms, validation.
- **Dependencies:** Target device with pose/depth source identified.
- **Output:** Spatial module and contracts update.
- **Acceptance criteria:** Transforms tested against known synthetic cases; unavailable when inputs missing.
- **Risks:** No depth/pose on target hardware.
- **Condition to proceed:** Feasibility study accepted.

## Phase 9: XR prototype

- **Goal:** Panel placement on a supported XR/AR platform.
- **Features:** Anchored info panel.
- **Dependencies:** Phase 8; platform chosen (Unity/AR Foundation, WebXR, etc.).
- **Output:** XR prototype.
- **Acceptance criteria:** Panel stays anchored in a manual test protocol.
- **Risks:** Platform fragmentation, device availability.
- **Condition to proceed:** Owner decides to proceed.

## Phase 10: Advanced spatial intelligence and future research

- **Goal:** Exploratory work.
- **Features:** Scene understanding, persistent anchors, multi-object reasoning.
- **Dependencies:** Phase 9.
- **Output:** Research notes, prototypes.
- **Acceptance criteria:** Defined per experiment.
- **Risks:** Scope creep.
- **Condition to proceed:** Per-experiment review.
