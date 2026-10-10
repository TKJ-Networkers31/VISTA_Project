# Decision Log

Do not change entries silently; supersede with a dated new entry.

## Fixed decisions (from the owner's briefs)
| ID | Decision | Reason | Consequence |
|---|---|---|---|
| D-1 | Project name VISTA; repo `VISTA` | Brief | — |
| D-2 | Python backend; Windows/PowerShell is primary dev environment | Brief | Docker/WSL/GPU/paid API not mandatory |
| D-3 | AI agents never commit/push/reset/clean without explicit instruction | Protect work | Human performs Git writes |
| D-4 | Raw images not retained by default | Privacy | Retention opt-in |
| D-5 | No fabricated results, detections, coordinates, benchmarks | Honesty | Unsupported → `not_implemented`/`unavailable` |
| D-6 | Modular monolith; hybrid provider-adapter inference; spatial boundaries | v0.2 brief | See ADR-0001/2/3 (ADRs still "Proposed" until owner marks Accepted) |
| D-7 | MVP = image upload + local OCR only; detection is Phase 3 | v0.2 brief supersedes v0.1 | Roadmap and spec updated |
| D-8 | Phase order 0–10 as in docs/ROADMAP.md | v0.2 brief supersedes v0.1 numbering | Prompt templates realigned |
| D-9 | Docs written in technical English | Cross-agent use | — |

## Proposals (not accepted)
2026-10-09 (Phase 3): ADR-0005 — YOLOX-Nano via ONNX Runtime as the detection backend, per-capability contract `0.3-detection`, shared `ModelManager` for OCR + detection (Proposed; owner marks Accepted). Ultralytics YOLO11n/YOLO26n judged AGPL-3.0/Enterprise and not adopted. YOLOX weights license and COCO terms need review. ADR-0004 (response envelope) is still undecided.

FastAPI; schema version 0.2 envelope; provisional limits in `.env.example`; Python 3.11; pytest + ruff dev tooling.

## Assumptions
A-1 X270, i7 7th gen, 8 GB RAM, CPU-only (verify on machine). A-2 Local OCR and a small detector are installable and fast enough. A-3 Android browser can reach the local server. A-4 Python 3.11 compatible with chosen libraries.

## Open questions
License (also gates the weights/AGPL question) · Review of YOLOX pretrained-weights and COCO terms · ADR-0004 envelope · OCR languages · external provider choice and cost ceiling · XR/Android target · security contact · LAN auth mechanism · resource-pressure thresholds.
