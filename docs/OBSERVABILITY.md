# Observability

Goal: understand behavior and resource use without leaking user content.

- **Logging:** structured logs with `request_id`, task state, capability, provider id, status, error category, durations. Not logged by default: image bytes, audio, OCR text, prompts, API keys. Redaction on by default (`VISTA_LOG_REDACT`).
- **Metrics (proposed):** queue depth, rejected tasks, task duration per capability, timeouts, cancellations, dropped frames (Phase 5), model load/unload events, resident memory, external call count and failures.
- **Health:** `/health` reports service state, capability registry, resident models, queue depth, and resource-pressure flag.
- **Tracing:** `request_id` propagated through every task and error.
- **Benchmarks:** collected by scripts in `scripts/` (future) with hardware/software metadata; never fabricated.
- **Retention:** logs are local, rotated, and git-ignored.
