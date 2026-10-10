# VISTA

**Visual Intelligence & Spatial Technology Architecture**

> **Status: Phase 0 — foundation only.** The repository contains documentation, contracts, rules, and configuration. **No application feature is implemented.** See [CHANGELOG.md](CHANGELOG.md).

## Purpose
VISTA is a modular visual intelligence platform intended to grow from image OCR toward object detection, live camera analysis, voice interaction, tracking, and — in the long term — spatial AR/MR/XR interfaces. The long-term vision (point a camera, ask by voice, get grounded analysis anchored in space) is **not available today**.

## Capability status
| Capability | Status |
|---|---|
| Image upload + OCR (local) | Planned — Phases 1–2 (MVP) |
| Object detection (local, YOLOX-Nano via ONNX Runtime) | Implemented in Phase 3, verified in a Linux sandbox only; model file installed separately; **not validated on the X270** — see [docs/DETECTION.md](docs/DETECTION.md) |
| Hybrid/external providers, image understanding | Planned — Phase 4 |
| Live camera | Planned — Phase 5 |
| Voice (STT/intent/TTS) | Planned — Phase 6 |
| Tracking, depth/pose | Planned — Phase 7 (optional/experimental) |
| Spatial 3D, AR/MR/XR, Android | Future/experimental — Phases 8–9 |
| Anything above implemented | OCR (Phases 1–2) and detection (Phase 3) have code and tests; Windows/X270 validation is still pending. Everything else: **none** |

Nothing is "experimental" yet because nothing is built; unsupported spatial features report `not_implemented`.

## Architecture overview
Modular monolith in Python. Clients → API → orchestration (capability registry, bounded queue, routing policy) → provider adapters (local or external) → normalized contracts → response. Details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/PROCESS_FLOWS.md](docs/PROCESS_FLOWS.md), [docs/DATA_CONTRACTS.md](docs/DATA_CONTRACTS.md).

## Target hardware
Lenovo ThinkPad X270, Core i7 7th gen, 8 GB RAM, Windows, CPU-only assumed. No GPU, Docker, WSL, or paid API required. See [docs/RESOURCE_BUDGET.md](docs/RESOURCE_BUDGET.md).

## Windows setup (PowerShell)
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```
Full guide and troubleshooting: [docs/WINDOWS_SETUP.md](docs/WINDOWS_SETUP.md).

## Configuration
Environment variables with provisional defaults: [docs/CONFIGURATION.md](docs/CONFIGURATION.md). `.env` is git-ignored; never commit secrets.

## Testing
```powershell
python -m pytest
python -m ruff check .
```
At Phase 0 there are no tests (pytest reports none collected). Test policy: [docs/TEST_STRATEGY.md](docs/TEST_STRATEGY.md).

## Security warnings
Default bind is localhost. External AI services are off by default and never receive images, audio, or text without explicit configuration. See [docs/SECURITY_AND_PRIVACY.md](docs/SECURITY_AND_PRIVACY.md) and [SECURITY.md](SECURITY.md).

## Roadmap
Phases 0–10 in [docs/ROADMAP.md](docs/ROADMAP.md). No phase counts as complete without evidence.

## Documentation index
[Detection](docs/DETECTION.md) · [Overview](docs/PROJECT_OVERVIEW.md) · [Product spec](docs/PRODUCT_SPEC.md) · [Tech stack](docs/TECH_STACK.md) · [File tree](docs/FILE_TREE.md) · [Provider policy](docs/API_PROVIDER_POLICY.md) · [Errors](docs/ERROR_HANDLING.md) · [Observability](docs/OBSERVABILITY.md) · [Spatial plan](docs/SPATIAL_COMPUTING_PLAN.md) · [Dev workflow](docs/DEVELOPMENT_WORKFLOW.md) · [Planning notes](docs/PLANNING_NOTES.md) · [Glossary](docs/GLOSSARY.md) · [ADRs](docs/ADR/README.md) · [AI rules](ai/AI_WORKING_RULES.md) · [GitHub setup](GITHUB_SETUP.md)

## Contributing
[CONTRIBUTING.md](CONTRIBUTING.md) · [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)

## License
Not decided yet; see [LICENSE_DECISION.md](LICENSE_DECISION.md). Until a license is added, all rights are reserved by the owner.
