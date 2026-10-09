# Prompt Templates

Copy a block, fill in `<...>`, and give it to an AI coding agent. All prompts assume [AI_WORKING_RULES.md](AI_WORKING_RULES.md).

## Repository audit

```text
Role: careful software engineer on the VISTA project.

Scope: Audit the current repository state without modifying files.

Must read first: `ai/AI_WORKING_RULES.md`, `docs/ARCHITECTURE.md`, `docs/DATA_CONTRACTS.md`, `docs/ROADMAP.md`

Deliverables: Report: file inventory, git status/branch/remote/diff summary, doc-vs-code mismatches, risks.

Acceptance criteria: Report is accurate and based on commands actually run.

Prohibited: No scope creep: do not implement features from other phases, add unrequested dependencies, change architecture, or run Git commit/push/reset/clean.

Testing: Read-only commands only. Run the relevant tests and report the real commands and output. If you could not run something, say so. Never invent results.

Final report: files changed, tests run, actual results, limitations, open questions.
```

## Phase 1 — Backend skeleton

```text
Role: careful software engineer on the VISTA project.

Scope: Implement only the bootstrap: app factory, `GET /health`, config loading from env, structured error format, logging without image data. Not OCR or vision.

Must read first: `ai/AI_WORKING_RULES.md`, `docs/ARCHITECTURE.md`, `docs/DATA_CONTRACTS.md`, `docs/ROADMAP.md`, `docs/TECH_STACK.md`, `.env.example`

Deliverables: Minimal app files, dependency list with verified versions, tests, README setup section updated.

Acceptance criteria: AC-1 in `docs/PRODUCT_SPEC.md`; tests pass in a real run.

Prohibited: No scope creep: do not implement features from other phases, add unrequested dependencies, change architecture, or run Git commit/push/reset/clean.

Testing: Run pytest and start the app once to hit `/health`. Run the relevant tests and report the real commands and output. If you could not run something, say so. Never invent results.

Final report: files changed, tests run, actual results, limitations, open questions.
```

## Phase 2 — Image intake and OCR

```text
Role: careful software engineer on the VISTA project.

Scope: Add `POST /v1/analyze` with safe validation and an OCR provider behind an interface.

Must read first: `ai/AI_WORKING_RULES.md`, `docs/ARCHITECTURE.md`, `docs/DATA_CONTRACTS.md`, `docs/ROADMAP.md`, `docs/SECURITY_AND_PRIVACY.md`, `docs/TECH_STACK.md`

Deliverables: Validation, decoder, OCR provider, normalized output, fixtures, tests, measured latency/RAM.

Acceptance criteria: AC-2, AC-3, AC-4, AC-5; confidence `null` when provider gives none.

Prohibited: No scope creep: do not implement features from other phases, add unrequested dependencies, change architecture, or run Git commit/push/reset/clean.

Testing: Unit, API, contract tests; record measurements with hardware noted. Run the relevant tests and report the real commands and output. If you could not run something, say so. Never invent results.

Final report: files changed, tests run, actual results, limitations, open questions.
```

## Phase 3 — Object detection

```text
Role: careful software engineer on the VISTA project.

Scope: Add a detection provider behind an interface, same response contract.

Must read first: `ai/AI_WORKING_RULES.md`, `docs/ARCHITECTURE.md`, `docs/DATA_CONTRACTS.md`, `docs/ROADMAP.md`, `docs/TECH_STACK.md`

Deliverables: Provider, bbox mapping to original pixels, tests, license check note.

Acceptance criteria: Boxes valid in original pixel space; partial failure handled.

Prohibited: No scope creep: do not implement features from other phases, add unrequested dependencies, change architecture, or run Git commit/push/reset/clean.

Testing: Contract and integration tests with fixtures. Run the relevant tests and report the real commands and output. If you could not run something, say so. Never invent results.

Final report: files changed, tests run, actual results, limitations, open questions.
```

## Phase 4 — Web UI

```text
Role: careful software engineer on the VISTA project.

Scope: Build the responsive static UI: upload/capture, overlay, result lists, errors.

Must read first: `ai/AI_WORKING_RULES.md`, `docs/ARCHITECTURE.md`, `docs/DATA_CONTRACTS.md`, `docs/ROADMAP.md`, `docs/PRODUCT_SPEC.md`

Deliverables: `apps/web` files, manual test protocol results.

Acceptance criteria: Overlay aligned on laptop and Android; errors displayed.

Prohibited: No scope creep: do not implement features from other phases, add unrequested dependencies, change architecture, or run Git commit/push/reset/clean.

Testing: Describe manual checks actually performed. Run the relevant tests and report the real commands and output. If you could not run something, say so. Never invent results.

Final report: files changed, tests run, actual results, limitations, open questions.
```

## Phase 5 — Hardening

```text
Role: careful software engineer on the VISTA project.

Scope: Harden limits, temp files, schema validation, docs sync; prepare MVP.

Must read first: `ai/AI_WORKING_RULES.md`, `docs/ARCHITECTURE.md`, `docs/DATA_CONTRACTS.md`, `docs/ROADMAP.md`, `docs/SECURITY_AND_PRIVACY.md`, `docs/TEST_STRATEGY.md`

Deliverables: Security fixes, expanded tests, updated docs/CHANGELOG.

Acceptance criteria: All MVP acceptance criteria pass.

Prohibited: No scope creep: do not implement features from other phases, add unrequested dependencies, change architecture, or run Git commit/push/reset/clean.

Testing: Full test suite run and reported. Run the relevant tests and report the real commands and output. If you could not run something, say so. Never invent results.

Final report: files changed, tests run, actual results, limitations, open questions.
```

## Bug fixing

```text
Role: careful software engineer on the VISTA project.

Scope: Fix one reported bug with a failing test first.

Must read first: `ai/AI_WORKING_RULES.md`, `docs/ARCHITECTURE.md`, `docs/DATA_CONTRACTS.md`, `docs/ROADMAP.md`

Deliverables: Regression test, minimal fix, explanation of root cause.

Acceptance criteria: Test fails before and passes after (show both).

Prohibited: No scope creep: do not implement features from other phases, add unrequested dependencies, change architecture, or run Git commit/push/reset/clean.

Testing: Run the full suite. Run the relevant tests and report the real commands and output. If you could not run something, say so. Never invent results.

Final report: files changed, tests run, actual results, limitations, open questions.
```

## Code review

```text
Role: careful software engineer on the VISTA project.

Scope: Review a diff against `ai/REVIEW_CHECKLIST.md`; do not modify code.

Must read first: `ai/AI_WORKING_RULES.md`, `docs/ARCHITECTURE.md`, `docs/DATA_CONTRACTS.md`, `docs/ROADMAP.md`, `ai/REVIEW_CHECKLIST.md`

Deliverables: Findings by severity with file/line references.

Acceptance criteria: Every checklist item addressed.

Prohibited: No scope creep: do not implement features from other phases, add unrequested dependencies, change architecture, or run Git commit/push/reset/clean.

Testing: Read-only. Run the relevant tests and report the real commands and output. If you could not run something, say so. Never invent results.

Final report: files changed, tests run, actual results, limitations, open questions.
```

## Performance optimization

```text
Role: careful software engineer on the VISTA project.

Scope: Reduce measured latency or RAM for one named bottleneck.

Must read first: `ai/AI_WORKING_RULES.md`, `docs/ARCHITECTURE.md`, `docs/DATA_CONTRACTS.md`, `docs/ROADMAP.md`, `docs/TEST_STRATEGY.md`

Deliverables: Before/after measurements on the same hardware, minimal change.

Acceptance criteria: Improvement is measured; no accuracy regression on fixtures.

Prohibited: No scope creep: do not implement features from other phases, add unrequested dependencies, change architecture, or run Git commit/push/reset/clean.

Testing: Report real benchmarks only. Run the relevant tests and report the real commands and output. If you could not run something, say so. Never invent results.

Final report: files changed, tests run, actual results, limitations, open questions.
```

## Phase 6 — Live camera

```text
Role: careful software engineer on the VISTA project.

Scope: Prototype frame capture, bounded queue (drop oldest), inference loop, overlay.

Must read first: `ai/AI_WORKING_RULES.md`, `docs/ARCHITECTURE.md`, `docs/DATA_CONTRACTS.md`, `docs/ROADMAP.md`, `docs/PROCESS_FLOWS.md`

Deliverables: Prototype, memory-growth check, measured frame rate.

Acceptance criteria: No unbounded queue; stable under sustained load.

Prohibited: No scope creep: do not implement features from other phases, add unrequested dependencies, change architecture, or run Git commit/push/reset/clean.

Testing: Soak test with reported numbers. Run the relevant tests and report the real commands and output. If you could not run something, say so. Never invent results.

Final report: files changed, tests run, actual results, limitations, open questions.
```

## Phase 7 — Voice integration

```text
Role: careful software engineer on the VISTA project.

Scope: Add STT, target association, LLM, response path independent of the vision loop.

Must read first: `ai/AI_WORKING_RULES.md`, `docs/ARCHITECTURE.md`, `docs/DATA_CONTRACTS.md`, `docs/ROADMAP.md`, `docs/SECURITY_AND_PRIVACY.md`

Deliverables: Voice flow, provider ADR, prompt-injection handling for OCR text.

Acceptance criteria: Vision latency unchanged while LLM runs; OCR text treated as data.

Prohibited: No scope creep: do not implement features from other phases, add unrequested dependencies, change architecture, or run Git commit/push/reset/clean.

Testing: Measure vision loop with and without LLM active. Run the relevant tests and report the real commands and output. If you could not run something, say so. Never invent results.

Final report: files changed, tests run, actual results, limitations, open questions.
```

## Spatial computing feasibility study

```text
Role: careful software engineer on the VISTA project.

Scope: Research only: what pose, tracking, and depth sources exist on the target device; write findings, no code claims.

Must read first: `ai/AI_WORKING_RULES.md`, `docs/ARCHITECTURE.md`, `docs/DATA_CONTRACTS.md`, `docs/ROADMAP.md`, `docs/GLOSSARY.md`

Deliverables: Study document with sources and clearly labeled unknowns.

Acceptance criteria: No unverified claims; coordinate spaces kept distinct.

Prohibited: No scope creep: do not implement features from other phases, add unrequested dependencies, change architecture, or run Git commit/push/reset/clean.

Testing: No code; cite sources. Run the relevant tests and report the real commands and output. If you could not run something, say so. Never invent results.

Final report: files changed, tests run, actual results, limitations, open questions.
```

## Phase 9 — XR integration

```text
Role: careful software engineer on the VISTA project.

Scope: Prototype an anchored info panel on the chosen platform, only if the feasibility study approved it.

Must read first: `ai/AI_WORKING_RULES.md`, `docs/ARCHITECTURE.md`, `docs/DATA_CONTRACTS.md`, `docs/ROADMAP.md`, feasibility study

Deliverables: Prototype and manual test protocol.

Acceptance criteria: Panel anchored per protocol; 2D boxes never presented as 3D.

Prohibited: No scope creep: do not implement features from other phases, add unrequested dependencies, change architecture, or run Git commit/push/reset/clean.

Testing: Report manual test results honestly. Run the relevant tests and report the real commands and output. If you could not run something, say so. Never invent results.

Final report: files changed, tests run, actual results, limitations, open questions.
```
