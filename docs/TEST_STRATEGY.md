# Test Strategy

Rule: never report a test as passing unless it was actually run; report real output.

| Level | Scope | Phase |
|---|---|---|
| Unit | validation, normalization, coordinate mapping, config | 1+ |
| API | health, analyze success, each error code | 1–2 |
| Integration | real OCR/detector on fixtures; partial failure via fake providers | 2–3 |
| Contract | every response validates against the JSON Schema; examples in docs validate | 1+ |
| UI | overlay alignment, error display; manual protocol on laptop and Android | 4 |
| Performance | latency and peak RAM on the reference laptop; recorded as measurements with hardware noted | 2+ |

## Fixtures
Small, synthetic or self-owned, license-clear images under `tests/fixtures/`: printed-text image, object image, blank image, corrupt file, oversized-dimension image (generated). No personal data.

## Quality gates
- Phase 1: health and config tests pass.
- Phase 2: OCR fixture test, all validation error tests, no-retention test.
- Phase 3: detection contract test; bbox in original pixel space verified on scaled input.
- Phase 4: manual UI protocol completed on both clients.
- Phase 5: all acceptance criteria in [PRODUCT_SPEC.md](PRODUCT_SPEC.md), security checklist done.
- Phase 6+: gates defined in the phase task before work starts.
