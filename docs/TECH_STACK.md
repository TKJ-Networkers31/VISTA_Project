# Tech Stack

Nothing here is verified on the target machine yet. Versions are deliberately not pinned. Verify installability, license, and RAM before adopting.

## Chosen for MVP direction
| Area | Choice | Status |
|---|---|---|
| Language | Python | [Decision] |
| Backend | FastAPI (+ ASGI server) | [Proposal] |
| UI | HTML, CSS, JavaScript, responsive | [Proposal] |
| Tests | pytest | [Proposal] |

## Candidates
| Area | Candidate | Alternatives | Trade-offs |
|---|---|---|---|
| OCR | PaddleOCR | Tesseract, EasyOCR, RapidOCR | Accuracy vs install size, RAM, Windows compatibility |
| Detection | Small YOLO-family model | Other lightweight detectors via ONNX | Speed on CPU vs accuracy; **check model license** |
| Inference runtime | Engine default | ONNX Runtime | Lower dependencies/faster CPU vs conversion effort |
| Storage | None / SQLite if needed | — | Avoid persisting user data |
| STT/TTS/LLM | Open (Phase 7) | Local vs cloud | Privacy and cost vs quality |
| XR | Open (Phase 9) | Unity+AR Foundation, WebXR, RealityKit | Depends on target device |

## Impact notes (to be measured)
Deep-learning frameworks are the largest contributors to disk, RAM, and install complexity. Prefer one runtime if possible and lazy-load models.

## Criteria for final choice
Installs cleanly on Windows; fits RAM budget; acceptable measured latency; license compatible with the owner's chosen license; maintained; swappable behind the provider interface.
