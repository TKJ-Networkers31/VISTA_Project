# ADR-0004: Reconcile the OCR MVP response with DATA_CONTRACTS 0.2

- **Status:** Proposed (awaiting owner decision). Nothing in this ADR has been applied; the API is unchanged.
- **Date:** Post-MVP validation stage

## Context
Implementation Prompt 01 required a flat response (`request_id, status, filename, image_width, image_height, detected_text,
blocks, processing_time_ms, engine, warnings, error`). `docs/DATA_CONTRACTS.md` (schema `0.2`, a **[Proposal]** that "becomes real
when `core/contracts` is implemented") describes a different envelope. Both are the owner's documents; the code follows Prompt 01.

| Aspect | DATA_CONTRACTS 0.2 / PRODUCT_SPEC | Implemented MVP (`0.2-ocr-mvp`) |
|---|---|---|
| Endpoint | `POST /v1/analyze` (+ optional `options`: capabilities, policy) | `POST /api/v1/ocr` (+ `GET /api/v1/ocr/capabilities`) |
| `schema_version` | `"0.2"` | `"0.2-ocr-mvp"` |
| `status` values | succeeded, partial, failed, unavailable, not_implemented | succeeded, failed, unavailable |
| Payload | `result.{image{width,height,coordinate_space}, ocr.items[], detection, spatial}` | flat `image_width`, `image_height`, `coordinate_space`, `detected_text`, `blocks[]` |
| OCR item | `items[]`: text, confidence, bbox2d, optional polygon | `blocks[]`: same fields **plus** `line_index` |
| Errors | `errors[]` with `capability`, `provider_id` | single `error` object without those two fields |
| Timing | `timing_ms{decode,ocr,total}` | `processing_time_ms` (total only) |
| Capability map | `capabilities{ocr,detection,spatial}` in every response | only in `/api/v1/ocr/capabilities` (different shape: `ocr.engine`) |
| Detection / spatial | `detection: null`, `spatial: {status: not_implemented}` | fields absent |
| Raw output | not specified | optional `raw` (`include_raw=true`) |
| JSON Schema files | required by AC-4 (`core/contracts/`) | none yet (Pydantic models exist) |

Consequences today: AC-4 (validate against JSON Schema) and AC-6 (`spatial` reported `not_implemented`) cannot be demonstrated
literally; FR-2 names a different endpoint; FR-7 is met only by omission. Error codes, categories and HTTP mapping otherwise match
`ERROR_HANDLING.md`. A characterization test (`test_response_shape_is_the_documented_mvp_shape`) now fails if the shape changes silently.

## Options
**A. Keep the MVP shape; amend DATA_CONTRACTS.md** to document it as the implemented contract.
+ No code change, no client breakage. - Phase 3 (detection) needs multi-capability results, so the flat shape must change soon anyway; AC-4/AC-6 wording must be rewritten.

**B. Migrate the code to the 0.2 envelope now** (`/v1/analyze`, `result`, `errors[]`, `capabilities`).
+ Matches the written spec; one contract for all later phases. - Breaking change to the only client (own UI) and tests; contradicts Prompt 01 as written; done before a second capability exists to validate the design.

**C. Staged: keep the MVP shape now; add the envelope at `POST /v1/analyze` when the second capability (detection, Phase 3) arrives.**
`/api/v1/ocr` stays as a thin, versioned convenience view (or is deprecated) built from the same internal result.
+ No change now; the envelope is designed against two real capabilities; clients migrate once. - Two shapes coexist for a while; DATA_CONTRACTS.md needs an "implemented today" section in the meantime.

**D. Additive hybrid:** add `result`, `errors[]`, `capabilities`, `timing_ms` next to the flat fields in the current response.
+ Superset of both. - Duplicated data, ambiguous source of truth, larger payloads, permanent maintenance burden.

## Compatibility impact
A/C: none today. B: breaking for UI and tests (internal only so far; cost rises with every new client such as Android in Phase 9). D: non-breaking but permanently redundant.

## Recommendation
**Option C**, plus two non-breaking steps once approved: (1) add an "Implemented MVP contract (0.2-ocr-mvp)" section to
DATA_CONTRACTS.md and mark the 0.2 envelope as the Phase 3 target; (2) export JSON Schema from the Pydantic models into
`core/contracts/` and validate responses against it in tests (AC-4). Decide the final envelope with the owner before Phase 3 starts.

## Re-evaluation conditions
Before Phase 3 begins; if a client other than the bundled UI is built; if the `partial` status is needed earlier.
