# Prompt Templates

Copy a block, fill in `<...>`, and give it to an AI coding agent. All prompts assume [AI_WORKING_RULES.md](AI_WORKING_RULES.md). Phases follow [../docs/ROADMAP.md](../docs/ROADMAP.md).

## Repository audit

```text
Role: careful software engineer on VISTA (Windows, ThinkPad X270, 8 GB RAM, CPU-only assumption).

Scope: Read-only inspection of repo state, conventions, conflicts, secrets (never print secret values), and doc/code mismatches.

Must read first: `ai/AI_WORKING_RULES.md`, `docs/ARCHITECTURE.md`, `docs/DATA_CONTRACTS.md`, `docs/ROADMAP.md`, `docs/RESOURCE_BUDGET.md`

Deliverables: Written report with git status/branch/remote summary and risks.

Acceptance criteria: Report matches commands actually run.

Prohibited: No scope creep: no features from other phases, no unrequested dependencies, no architecture changes, no model weight downloads unless the task says so, and no Git commit/push/reset/clean.

Testing: Read-only commands only. Run only tests that exist and are meaningful; report exact commands and real output; say what was skipped. Normal tests must not need network, API keys, model weights, or GPU. Never invent results.

Final report: files changed, tests run, actual results, skipped checks, limitations, open questions.
```

## Phase 1 — Minimal API and image ingestion

```text
Role: careful software engineer on VISTA (Windows, ThinkPad X270, 8 GB RAM, CPU-only assumption).

Scope: App bootstrap, `/health`, capability registry, config (typed, validated), upload validation, error envelope, JSON Schemas, mock provider, bounded queue. No OCR.

Must read first: `ai/AI_WORKING_RULES.md`, `docs/ARCHITECTURE.md`, `docs/DATA_CONTRACTS.md`, `docs/ROADMAP.md`, `docs/RESOURCE_BUDGET.md`, `docs/CONFIGURATION.md`, `docs/ERROR_HANDLING.md`, `docs/WINDOWS_SETUP.md`

Deliverables: Code under `apps/api`, `core/contracts`, `core/orchestration`, `core/providers`, tests, updated WINDOWS_SETUP start command.

Acceptance criteria: AC-1, AC-3, AC-4, AC-5.

Prohibited: No scope creep: no features from other phases, no unrequested dependencies, no architecture changes, no model weight downloads unless the task says so, and no Git commit/push/reset/clean.

Testing: Unit, API, contract, security tests with mocks; run `python -m pytest`. Run only tests that exist and are meaningful; report exact commands and real output; say what was skipped. Normal tests must not need network, API keys, model weights, or GPU. Never invent results.

Final report: files changed, tests run, actual results, skipped checks, limitations, open questions.
```

## Phase 2 — OCR MVP

```text
Role: careful software engineer on VISTA (Windows, ThinkPad X270, 8 GB RAM, CPU-only assumption).

Scope: Local OCR provider behind the interface, deterministic mock-based tests, web upload page with overlay.

Must read first: `ai/AI_WORKING_RULES.md`, `docs/ARCHITECTURE.md`, `docs/DATA_CONTRACTS.md`, `docs/ROADMAP.md`, `docs/RESOURCE_BUDGET.md`, `docs/TECH_STACK.md`, `docs/SECURITY_AND_PRIVACY.md`

Deliverables: `core/ocr`, `apps/web`, fixtures, measured latency/RAM notes in RESOURCE_BUDGET.

Acceptance criteria: AC-2, AC-6, AC-7; unavailable status if engine missing.

Prohibited: No scope creep: no features from other phases, no unrequested dependencies, no architecture changes, no model weight downloads unless the task says so, and no Git commit/push/reset/clean.

Testing: Mock tests by default; real-engine test marked `requires_model`. Run only tests that exist and are meaningful; report exact commands and real output; say what was skipped. Normal tests must not need network, API keys, model weights, or GPU. Never invent results.

Final report: files changed, tests run, actual results, skipped checks, limitations, open questions.
```

## Phase 3 — Object detection

```text
Role: careful software engineer on VISTA (Windows, ThinkPad X270, 8 GB RAM, CPU-only assumption).

Scope: Lightweight detector provider, normalized output, measured resource use.

Must read first: `ai/AI_WORKING_RULES.md`, `docs/ARCHITECTURE.md`, `docs/DATA_CONTRACTS.md`, `docs/ROADMAP.md`, `docs/RESOURCE_BUDGET.md`, `docs/TECH_STACK.md`

Deliverables: Provider, contract update, measured numbers recorded (no invented numbers).

Acceptance criteria: Boxes map to original pixels; one-heavy-model default respected.

Prohibited: No scope creep: no features from other phases, no unrequested dependencies, no architecture changes, no model weight downloads unless the task says so, and no Git commit/push/reset/clean.

Testing: Contract tests, optional real-model benchmark. Run only tests that exist and are meaningful; report exact commands and real output; say what was skipped. Normal tests must not need network, API keys, model weights, or GPU. Never invent results.

Final report: files changed, tests run, actual results, skipped checks, limitations, open questions.
```

## Phase 4 — Hybrid providers and image understanding

```text
Role: careful software engineer on VISTA (Windows, ThinkPad X270, 8 GB RAM, CPU-only assumption).

Scope: External adapters, policy router, consent, retries and cost limits.

Must read first: `ai/AI_WORKING_RULES.md`, `docs/ARCHITECTURE.md`, `docs/DATA_CONTRACTS.md`, `docs/ROADMAP.md`, `docs/RESOURCE_BUDGET.md`, `docs/API_PROVIDER_POLICY.md`, `docs/SECURITY_AND_PRIVACY.md`

Deliverables: Adapters, router, consent gating, redaction.

Acceptance criteria: `local_only`/`hybrid`/`external_fallback` behave as documented; bounded retries.

Prohibited: No scope creep: no features from other phases, no unrequested dependencies, no architecture changes, no model weight downloads unless the task says so, and no Git commit/push/reset/clean.

Testing: Adapter tests with fakes; no network or keys. Run only tests that exist and are meaningful; report exact commands and real output; say what was skipped. Normal tests must not need network, API keys, model weights, or GPU. Never invent results.

Final report: files changed, tests run, actual results, skipped checks, limitations, open questions.
```

## Phase 5 — Live camera

```text
Role: careful software engineer on VISTA (Windows, ThinkPad X270, 8 GB RAM, CPU-only assumption).

Scope: Frame sampling, bounded queue with drop-oldest, cancellation; camera path never awaits external AI.

Must read first: `ai/AI_WORKING_RULES.md`, `docs/ARCHITECTURE.md`, `docs/DATA_CONTRACTS.md`, `docs/ROADMAP.md`, `docs/RESOURCE_BUDGET.md`, `docs/PROCESS_FLOWS.md`

Deliverables: Prototype and soak-test results.

Acceptance criteria: Bounded memory; cancellation works.

Prohibited: No scope creep: no features from other phases, no unrequested dependencies, no architecture changes, no model weight downloads unless the task says so, and no Git commit/push/reset/clean.

Testing: Queue unit tests; reported soak measurements. Run only tests that exist and are meaningful; report exact commands and real output; say what was skipped. Normal tests must not need network, API keys, model weights, or GPU. Never invent results.

Final report: files changed, tests run, actual results, skipped checks, limitations, open questions.
```

## Phase 6 — Voice integration

```text
Role: careful software engineer on VISTA (Windows, ThinkPad X270, 8 GB RAM, CPU-only assumption).

Scope: STT, intent routing, TTS adapters on a path separate from vision.

Must read first: `ai/AI_WORKING_RULES.md`, `docs/ARCHITECTURE.md`, `docs/DATA_CONTRACTS.md`, `docs/ROADMAP.md`, `docs/RESOURCE_BUDGET.md`, `docs/API_PROVIDER_POLICY.md`

Deliverables: Voice flow with grounded answers.

Acceptance criteria: Vision loop unaffected; audio not retained by default.

Prohibited: No scope creep: no features from other phases, no unrequested dependencies, no architecture changes, no model weight downloads unless the task says so, and no Git commit/push/reset/clean.

Testing: Adapter and intent tests with mocks. Run only tests that exist and are meaningful; report exact commands and real output; say what was skipped. Normal tests must not need network, API keys, model weights, or GPU. Never invent results.

Final report: files changed, tests run, actual results, skipped checks, limitations, open questions.
```

## Phase 7 — Tracking and optional depth/pose

```text
Role: careful software engineer on VISTA (Windows, ThinkPad X270, 8 GB RAM, CPU-only assumption).

Scope: Tracker with `track_id`; depth/pose as separate optional providers.

Must read first: `ai/AI_WORKING_RULES.md`, `docs/ARCHITECTURE.md`, `docs/DATA_CONTRACTS.md`, `docs/ROADMAP.md`, `docs/RESOURCE_BUDGET.md`, `docs/SPATIAL_COMPUTING_PLAN.md`

Deliverables: Tracker, contract update, capability statuses.

Acceptance criteria: Stable IDs on a defined synthetic sequence; depth/pose `unavailable` if absent.

Prohibited: No scope creep: no features from other phases, no unrequested dependencies, no architecture changes, no model weight downloads unless the task says so, and no Git commit/push/reset/clean.

Testing: Tracking tests on synthetic data. Run only tests that exist and are meaningful; report exact commands and real output; say what was skipped. Normal tests must not need network, API keys, model weights, or GPU. Never invent results.

Final report: files changed, tests run, actual results, skipped checks, limitations, open questions.
```

## Phase 8 — Spatial feasibility and architecture

```text
Role: careful software engineer on VISTA (Windows, ThinkPad X270, 8 GB RAM, CPU-only assumption).

Scope: Study then implement validated transforms only if feasible; follow ADR-0003.

Must read first: `ai/AI_WORKING_RULES.md`, `docs/ARCHITECTURE.md`, `docs/DATA_CONTRACTS.md`, `docs/ROADMAP.md`, `docs/RESOURCE_BUDGET.md`, `docs/SPATIAL_COMPUTING_PLAN.md`, `docs/ADR/ADR-0003-spatial-capability-boundaries.md`

Deliverables: Feasibility document; code only if approved.

Acceptance criteria: Transforms validated vs synthetic ground truth; nothing simulated.

Prohibited: No scope creep: no features from other phases, no unrequested dependencies, no architecture changes, no model weight downloads unless the task says so, and no Git commit/push/reset/clean.

Testing: Math unit tests; cite sources. Run only tests that exist and are meaningful; report exact commands and real output; say what was skipped. Normal tests must not need network, API keys, model weights, or GPU. Never invent results.

Final report: files changed, tests run, actual results, skipped checks, limitations, open questions.
```

## Phase 9 — Android and XR integration

```text
Role: careful software engineer on VISTA (Windows, ThinkPad X270, 8 GB RAM, CPU-only assumption).

Scope: Android client and XR experiments using the same API contract.

Must read first: `ai/AI_WORKING_RULES.md`, `docs/ARCHITECTURE.md`, `docs/DATA_CONTRACTS.md`, `docs/ROADMAP.md`, `docs/RESOURCE_BUDGET.md`, feasibility study

Deliverables: Prototype and manual test protocol.

Acceptance criteria: 2D boxes never presented as 3D.

Prohibited: No scope creep: no features from other phases, no unrequested dependencies, no architecture changes, no model weight downloads unless the task says so, and no Git commit/push/reset/clean.

Testing: Contract tests; manual device checks reported honestly. Run only tests that exist and are meaningful; report exact commands and real output; say what was skipped. Normal tests must not need network, API keys, model weights, or GPU. Never invent results.

Final report: files changed, tests run, actual results, skipped checks, limitations, open questions.
```

## Bug fixing

```text
Role: careful software engineer on VISTA (Windows, ThinkPad X270, 8 GB RAM, CPU-only assumption).

Scope: Fix one reported bug, failing test first.

Must read first: `ai/AI_WORKING_RULES.md`, `docs/ARCHITECTURE.md`, `docs/DATA_CONTRACTS.md`, `docs/ROADMAP.md`, `docs/RESOURCE_BUDGET.md`

Deliverables: Regression test and minimal fix with root cause.

Acceptance criteria: Test fails before and passes after (show both).

Prohibited: No scope creep: no features from other phases, no unrequested dependencies, no architecture changes, no model weight downloads unless the task says so, and no Git commit/push/reset/clean.

Testing: Run the full suite. Run only tests that exist and are meaningful; report exact commands and real output; say what was skipped. Normal tests must not need network, API keys, model weights, or GPU. Never invent results.

Final report: files changed, tests run, actual results, skipped checks, limitations, open questions.
```

## Code review

```text
Role: careful software engineer on VISTA (Windows, ThinkPad X270, 8 GB RAM, CPU-only assumption).

Scope: Review a diff with `ai/REVIEW_CHECKLIST.md`; no edits.

Must read first: `ai/AI_WORKING_RULES.md`, `docs/ARCHITECTURE.md`, `docs/DATA_CONTRACTS.md`, `docs/ROADMAP.md`, `docs/RESOURCE_BUDGET.md`, `ai/REVIEW_CHECKLIST.md`

Deliverables: Findings by severity with file/line.

Acceptance criteria: Every checklist item addressed.

Prohibited: No scope creep: no features from other phases, no unrequested dependencies, no architecture changes, no model weight downloads unless the task says so, and no Git commit/push/reset/clean.

Testing: Read-only. Run only tests that exist and are meaningful; report exact commands and real output; say what was skipped. Normal tests must not need network, API keys, model weights, or GPU. Never invent results.

Final report: files changed, tests run, actual results, skipped checks, limitations, open questions.
```

## Performance optimization

```text
Role: careful software engineer on VISTA (Windows, ThinkPad X270, 8 GB RAM, CPU-only assumption).

Scope: Improve one measured bottleneck.

Must read first: `ai/AI_WORKING_RULES.md`, `docs/ARCHITECTURE.md`, `docs/DATA_CONTRACTS.md`, `docs/ROADMAP.md`, `docs/RESOURCE_BUDGET.md`

Deliverables: Before/after measurements on the same hardware.

Acceptance criteria: Improvement measured; no regression on fixtures.

Prohibited: No scope creep: no features from other phases, no unrequested dependencies, no architecture changes, no model weight downloads unless the task says so, and no Git commit/push/reset/clean.

Testing: Real benchmarks only. Run only tests that exist and are meaningful; report exact commands and real output; say what was skipped. Normal tests must not need network, API keys, model weights, or GPU. Never invent results.

Final report: files changed, tests run, actual results, skipped checks, limitations, open questions.
```

## Phase 10 — Hardening and release

```text
Role: careful software engineer on VISTA (Windows, ThinkPad X270, 8 GB RAM, CPU-only assumption).

Scope: Security review, optimization, deployment guide.

Must read first: `ai/AI_WORKING_RULES.md`, `docs/ARCHITECTURE.md`, `docs/DATA_CONTRACTS.md`, `docs/ROADMAP.md`, `docs/RESOURCE_BUDGET.md`, `docs/SECURITY_AND_PRIVACY.md`

Deliverables: Review report, deployment docs.

Acceptance criteria: Earlier acceptance criteria re-verified.

Prohibited: No scope creep: no features from other phases, no unrequested dependencies, no architecture changes, no model weight downloads unless the task says so, and no Git commit/push/reset/clean.

Testing: Full suite, security tests, benchmarks. Run only tests that exist and are meaningful; report exact commands and real output; say what was skipped. Normal tests must not need network, API keys, model weights, or GPU. Never invent results.

Final report: files changed, tests run, actual results, skipped checks, limitations, open questions.
```
