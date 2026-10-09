# Decision Log

Do not change entries silently; supersede with a dated new entry.

## Fixed decisions
| ID | Decision | Reason | Consequence |
|---|---|---|---|
| D-1 | Project name VISTA; repo name `VISTA` | Project brief | — |
| D-2 | Python backend | Project brief | Python tooling |
| D-3 | AI agents must not commit/push/destroy without explicit instruction | Protect owner work | Human performs Git writes |
| D-4 | Raw images not retained by default | Privacy | Retention is opt-in |
| D-5 | No fabricated results or benchmarks | Honesty | Real runs only |

## Proposals (not yet accepted)
| ID | Proposal | Trade-off |
|---|---|---|
| P-1 | Modular monolith ([ADR-0001](../docs/ADR/ADR-0001-modular-monolith.md)) | Simplicity vs shared-process RAM |
| P-2 | FastAPI backend | Familiar/async vs extra dependency |
| P-3 | Schema version 0.1 per [DATA_CONTRACTS](../docs/DATA_CONTRACTS.md) | Needs validation in Phase 1–2 |

## Assumptions
A-1 Reference hardware is i7-7th gen / 8 GB. A-2 PaddleOCR and a small YOLO-family model are installable and fast enough. A-3 Android browser can reach the local server.

## Open questions
License · OCR languages · XR target device · local vs cloud LLM/STT · security contact.
