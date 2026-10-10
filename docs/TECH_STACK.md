# Tech Stack

Nothing is verified on the X270 yet. Versions are not pinned. Verify installability on Windows, license, RAM, and CPU latency before adopting.

## Selected direction
| Area | Choice | Status |
|---|---|---|
| Language | Python (3.11 preferred; check installed version and compatibility) | [Proposal] |
| Backend | FastAPI | [Proposal] |
| Web UI | HTML/CSS/JS, responsive | [Proposal] |
| Tests/lint | pytest, ruff (dev only) | [Decision for dev tooling] |

## Candidates
| Area | Candidate | Alternatives | Trade-offs |
|---|---|---|---|
| Image processing | OpenCV (or Pillow) | Pillow only | Features vs install size |
| OCR | PaddleOCR | Tesseract, EasyOCR, RapidOCR | Accuracy vs size/RAM/Windows install |
| Detection | **YOLOX-Nano (ONNX Runtime) — implemented in Phase 3, see [ADR-0005](ADR/ADR-0005-detection-backend-and-model-residency.md) (Proposed)** | Ultralytics YOLO11n/YOLO26n (AGPL-3.0/Enterprise, not adopted) | CPU speed vs accuracy; weights license needs owner review |
| Runtime | Engine default | ONNX Runtime | Fewer deps/faster CPU vs conversion effort |
| STT/TTS/LLM/Vision | Provider adapters (local or external) | — | Privacy/cost vs capability |
| Storage | Filesystem temp; SQLite only if needed | — | Avoid persisting user data |
| Android / XR | Open | AR Foundation, ARCore, WebXR | Depends on device |

## Decision process
For each pick: shortlist → install test on the X270 → measure RAM/latency on fixtures → license check → record an ADR. No heavy models are downloaded for foundation work.

## Impact notes
Deep-learning frameworks dominate disk, RAM, and install risk; keep one heavy model resident by default; lazy-load; prefer fewer runtimes.
