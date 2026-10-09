# Test Strategy

Rules: never claim a test passed unless it was run and its output observed. Normal test runs require **no** API keys, network, downloaded model weights, or GPU. Provider-dependent tests are marked `requires_model` / `requires_network` and excluded by default (see `pyproject.toml`).

| Level | Scope | Phase |
|---|---|---|
| Unit | validation, normalization, coordinate mapping, queue behavior, config | 1+ |
| API | `/health`, `/v1/analyze`, each error code | 1+ |
| Integration | pipeline with mock providers; optional real-engine runs on fixtures | 2+ |
| Contract | every response and every doc example validates against JSON Schema | 1+ |
| Provider-adapter | adapters against fakes: timeouts, quota, auth, malformed responses | 4+ |
| Security | oversize/over-pixel/corrupt files, path traversal, no raw-image retention, log redaction, consent gating | 1+ |
| Performance | latency, peak RAM, throughput on reference laptop; recorded with hardware info | 2+ |

## Mock providers
Deterministic mock OCR/detection/LLM/STT/TTS providers live with `core/providers` and drive all default tests, including failure modes (timeout, unavailable, malformed output).

## Fixtures
Small, synthetic or self-owned, license-clear files in `tests/fixtures/`: printed-text image, blank image, corrupt file, generated oversized-dimension image. No personal data.

## Quality gates
- Phase 1: health, config, validation, contract tests pass in a real run.
- Phase 2: mock-OCR determinism, security tests, one measured real-OCR run recorded.
- Phase 3: detection contract, bbox mapping, measured resource use recorded.
- Phase 4: adapter and consent/redaction tests pass without network.
- Phase 5: bounded-memory soak test results recorded.
- Later phases: gates defined in the phase task before work starts.
