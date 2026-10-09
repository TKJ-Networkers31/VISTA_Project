# VISTA

**Visual Intelligence & Spatial Technology Architecture**

> Status: **Phase 0 — planning and repository foundation.** No OCR, detection, tracking, voice, or spatial feature is implemented yet. See [CHANGELOG.md](CHANGELOG.md).

VISTA is a planned visual AI platform that understands images and environments step by step: OCR, computer vision, object detection, tracking, real-time camera analysis, voice interaction, and — long term — spatial computing and AR/MR.

## Long-term vision (not available today)

A user points a smartphone or XR device at an object, VISTA detects and tracks it, the user asks a question by voice ("Describe what I am looking at"), VISTA answers from visual evidence, and the answer appears as an information panel (2D first, spatial 3D panel only when valid tracking and coordinates exist).

## Problem

Reading text and identifying objects in images usually needs several disconnected tools. VISTA aims to provide one modular, privacy-conscious pipeline that runs on modest hardware.

## Goals and non-goals

Goals: staged, testable milestones; consistent data contracts; low-resource operation (Core i7 7th gen, 8 GB RAM); privacy by default.

Non-goals (for now): microservices, cloud training, custom model training, claiming 3D understanding from 2D detections, permanent raw image storage.

## Features by phase

| Phase | Capability | Status |
|---|---|---|
| 0 | Documentation and repo foundation | In progress |
| 1 | Backend skeleton, health endpoint | Planned |
| 2 | Image intake and OCR | Planned |
| 3 | Object detection | Planned |
| 4 | Responsive web interface | Planned |
| 5 | Integration, security, MVP release | Planned |
| 6–10 | Live camera, voice, spatial, XR, research | Future |

Details: [docs/ROADMAP.md](docs/ROADMAP.md).

## Architecture (high level)

Client → API → validation → decoding/preprocessing → analysis orchestrator → OCR + detection providers → normalized contracts → response → web overlay. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Tech stack (candidates, unverified)

Python, FastAPI, PaddleOCR (or compatible alternative), small YOLO-family detector (or alternative), HTML/CSS/JS UI, SQLite only if needed. See [docs/TECH_STACK.md](docs/TECH_STACK.md). Versions are intentionally not pinned until compatibility is verified.

## Repository structure

See [docs/FILE_TREE.md](docs/FILE_TREE.md). Only documentation, `ai/`, and root configuration exist at v0.1.

## Prerequisites

- Python 3.10+ (exact version to be fixed in Phase 1 after dependency verification)
- Git
- Windows laptop is the reference development machine

## Setup and testing

There is nothing to install or test yet. Setup and test commands will be added in Phase 1 when code exists.

## Documentation

- [Project overview](docs/PROJECT_OVERVIEW.md) · [Product spec](docs/PRODUCT_SPEC.md) · [Architecture](docs/ARCHITECTURE.md)
- [Process flows](docs/PROCESS_FLOWS.md) · [Roadmap](docs/ROADMAP.md) · [Data contracts](docs/DATA_CONTRACTS.md)
- [Security and privacy](docs/SECURITY_AND_PRIVACY.md) · [Test strategy](docs/TEST_STRATEGY.md) · [Tech stack](docs/TECH_STACK.md)
- [Development workflow](docs/DEVELOPMENT_WORKFLOW.md) · [Planning notes](docs/PLANNING_NOTES.md) · [Glossary](docs/GLOSSARY.md)
- [ADR index](docs/ADR/README.md) · [AI working rules](ai/AI_WORKING_RULES.md) · [GitHub setup](GITHUB_SETUP.md)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Report vulnerabilities per [SECURITY.md](SECURITY.md).

## License

Not yet decided. See [LICENSE_DECISION.md](LICENSE_DECISION.md). Until a license is added, all rights are reserved by the project owner.

## Screenshots

None yet. Screenshots will be added only from the real application.
