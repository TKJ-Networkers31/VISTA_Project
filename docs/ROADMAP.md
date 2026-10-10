# Roadmap

No phase is complete without evidence (test output, measurements, or review notes) attached to the change. Any time estimate must be marked as a preliminary guess; none are given here. Phase order follows the v0.2 master prompt and supersedes the v0.1 numbering.

## Phase 0 — Repository foundation, requirements, architecture, contracts, and Windows setup

- **Goals:** Establish docs, contracts, rules, config.
- **Dependencies:** None.
- **Deliverables:** Documentation set, AI rules, root config, planned directory READMEs.
- **Acceptance criteria:** Links resolve; Mermaid/JSON/TOML validated; open decisions listed.
- **Tests:** Link/syntax validation only; no application tests exist.
- **Risks:** Documents drift or contradict.
- **Exit conditions:** Owner reviews v0.2 and records decisions in `ai/DECISION_LOG.md`.

## Phase 1 — Minimal API and image ingestion

- **Goals:** Bootstrap app, `/health`, capability registry, config, upload validation, error envelope.
- **Dependencies:** Phase 0; Python version and FastAPI compatibility verified on the X270.
- **Deliverables:** App skeleton, validation, JSON Schemas, mock provider.
- **Acceptance criteria:** AC-1, AC-3, AC-4, AC-5 in PRODUCT_SPEC.
- **Tests:** Unit, API, contract, security (limits) tests using mocks; no network/models.
- **Risks:** Windows dependency issues; limits set too loose.
- **Exit conditions:** Tests actually run and pass; dependency versions recorded; evidence attached to the PR.

## Phase 2 — OCR MVP with a local implementation and deterministic tests

- **Goals:** Local OCR behind the provider interface; web UI for upload/overlay.
- **Dependencies:** Phase 1; local OCR engine verified to install and run on target hardware.
- **Deliverables:** OCR provider, fixtures, web page, measured latency/RAM.
- **Acceptance criteria:** AC-2, AC-6, AC-7.
- **Tests:** Mock-provider tests (deterministic) plus an optional marked test using the real engine and fixtures.
- **Risks:** OCR install size/RAM on 8 GB; accuracy on real photos.
- **Exit conditions:** Measured resource use acceptable to owner or alternative chosen via ADR; MVP review.

## Phase 3 — Object detection with a lightweight model and measured resource use

**Status (2026-10-09): implemented; sandbox-verified only.** Contract, provider, orchestration, API, shared residency, tests and benchmark script exist (see [DETECTION.md](DETECTION.md)). **Open exit conditions:** X270 measurements recorded in RESOURCE_BUDGET.md, and the weights license confirmed by the owner. Not complete until both are done.

- **Goals:** Detection provider, normalized output, resource measurement.
- **Dependencies:** Phase 2; model and license verified.
- **Deliverables:** Detector provider, contract update, benchmark notes (measured).
- **Acceptance criteria:** Boxes correct in original pixel space; coexistence with OCR within RAM budget (one heavy model resident by default).
- **Tests:** Contract, integration (mock), optional real-model test, benchmark run.
- **Risks:** CPU latency; model license.
- **Exit conditions:** Measured numbers recorded in RESOURCE_BUDGET.md; license confirmed.

## Phase 4 — Hybrid provider adapters and image understanding

- **Goals:** External adapters, routing policies, cost/retry limits, consent gating.
- **Dependencies:** Phase 3; provider choice decided via ADR.
- **Deliverables:** Adapter interface implementations, policy router, image-understanding capability.
- **Acceptance criteria:** Policies `local_only`/`hybrid`/`external_fallback` behave as documented; no data leaves without consent; retries bounded.
- **Tests:** Provider-adapter tests with mocks/fakes (no keys or network); security tests for consent and redaction.
- **Risks:** Cost, privacy, quota errors, provider drift.
- **Exit conditions:** Policy tests pass; data-transmission visibility implemented.

## Phase 5 — Live camera, sampled frames, backpressure, and cancellation

- **Goals:** Frame sampling, bounded queue, drop policy, cancellation.
- **Dependencies:** Phase 3 benchmarks; browser camera access plan.
- **Deliverables:** Live prototype with bounded memory.
- **Acceptance criteria:** Memory stays bounded under sustained load; cancellation works; camera loop never blocks on external AI.
- **Tests:** Queue/backpressure unit tests; soak test with reported measurements.
- **Risks:** CPU too slow; HTTPS requirement for phone camera access.
- **Exit conditions:** Measured sustainable frame rate recorded.

## Phase 6 — Voice interaction, STT, intent routing, and TTS

- **Goals:** Voice path in parallel with vision.
- **Dependencies:** Phases 4–5.
- **Deliverables:** STT/TTS adapters, intent router, grounded answers.
- **Acceptance criteria:** Vision loop latency unaffected by LLM/voice activity; audio not retained by default.
- **Tests:** Adapter and intent tests with mocks; latency comparison measured.
- **Risks:** Provider cost/privacy; hallucination.
- **Exit conditions:** Evidence of unaffected vision loop.

## Phase 7 — Object tracking, temporal context, and optional depth/pose capabilities

- **Goals:** Tracker, scene state, optional depth/pose as separate providers.
- **Dependencies:** Phase 5.
- **Deliverables:** Tracking provider, `track_id` in contracts, capability statuses for depth/pose.
- **Acceptance criteria:** Track IDs stable on a defined test sequence; depth/pose reported `unavailable` if absent.
- **Tests:** Tracking tests on synthetic sequences; contract tests.
- **Risks:** Identity switches; CPU cost.
- **Exit conditions:** Test sequences pass with recorded metrics.

## Phase 8 — Spatial computing architecture and experimental 3D overlays

- **Goals:** Coordinate transforms and anchors per ADR-0003.
- **Dependencies:** Phase 7; real pose/depth source exists on target device.
- **Deliverables:** Spatial module, validated transforms, experimental overlay.
- **Acceptance criteria:** Transform tests against synthetic ground truth; capability stays `not_implemented`/`unavailable` without valid sources.
- **Tests:** Math/unit tests; manual protocol.
- **Risks:** No depth/pose hardware.
- **Exit conditions:** Feasibility and validation evidence accepted by owner.

## Phase 9 — Android integration and broader AR/MR/XR experimentation

- **Goals:** Android client and XR experiments.
- **Dependencies:** Phase 8.
- **Deliverables:** Android client prototype; XR experiment reports.
- **Acceptance criteria:** Client uses the same API contract; manual test protocol passes.
- **Tests:** Contract tests; manual device tests.
- **Risks:** Platform fragmentation; device availability.
- **Exit conditions:** Owner decision per experiment.

## Phase 10 — Performance optimization, security review, deployment, and product readiness

- **Goals:** Optimization, review, packaging.
- **Dependencies:** Phases 1–9 as relevant.
- **Deliverables:** Security review report, deployment guide, release.
- **Acceptance criteria:** All earlier acceptance criteria re-verified; known issues documented.
- **Tests:** Full test suite, security tests, benchmarks.
- **Risks:** Hidden resource or security issues.
- **Exit conditions:** Release sign-off with evidence.
