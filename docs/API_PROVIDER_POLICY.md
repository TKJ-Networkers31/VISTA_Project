# API and Provider Policy

Governing decision: [ADR-0002](ADR/ADR-0002-hybrid-inference.md).

## Provider interface (every provider exposes)
Provider id and model identity · supported capabilities · availability/readiness (health check) · required configuration · timeout and cancellation behavior · error categories · latency/resource metadata when measurable · `locality`: `local` or `external`.

## Policies
- **local_only (default):** only local providers. If none is ready → `unavailable`.
- **hybrid:** explicit per-capability routing table (e.g. OCR local, image understanding external). Routing lives in config, never implicit.
- **external_fallback:** try local first; call external only on local failure/unavailability **and** when allowed by consent, network, quota, and cost limits.

## Honest degradation
No suitable provider → structured `unavailable`/`failed`. Never invent OCR text, detections, coordinates, model results, or tool results.

## Limits
Per-call timeout; retry cap with backoff; daily call/cost ceiling (Phase 4); circuit breaker after repeated failures. Never retry indefinitely.

## Privacy and consent
Images, audio, documents, and extracted text are **not** sent externally unless: `VISTA_EXTERNAL_ENABLED=true`, a provider and policy are configured, and the request's policy permits it. Each external transmission is visible to the application (logged as metadata: provider, capability, size, timestamp; not content) and surfaced in the response `capabilities` metadata (`locality: external`).

## Secrets
Keys only in private `.env`/OS environment; never in source, logs, error messages, or fixtures.

## Capability requirements summary
| Capability | Local possible on X270? | External needed? |
|---|---|---|
| OCR | Expected (verify) | Optional |
| Object detection | Expected with small model (verify) | Optional |
| Image understanding / LLM | Unlikely locally | Likely, with credentials and network |
| STT/TTS | Small local models possible (verify) | Optional |
| Depth/pose/spatial | Device-dependent | No |
