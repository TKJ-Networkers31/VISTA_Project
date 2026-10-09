# Project Overview

Labels: **[Decision]**, **[Proposal]**, **[Assumption]**, **[Open]**.

## Vision
A user points a camera at an object, asks a question by voice, receives grounded visual analysis, and eventually interacts with contextual information anchored in a spatial interface. This is long-term; the MVP is image OCR only.

## Target experience
MVP: upload an image, see extracted text with boxes. Later: live camera overlays, voice Q&A, tracking, spatial panels on AR/MR/XR devices.

## Scope
Staged capabilities: OCR → detection → hybrid providers/image understanding → live camera → voice → tracking → spatial → Android/XR ([ROADMAP.md](ROADMAP.md)).

## Non-goals
Microservices/Kubernetes, model training, claiming 3D/spatial support before validation, mandatory GPU/Docker/WSL/paid APIs, permanent raw image storage.

## Major use cases
Read text from an image; (later) detect objects; ask about what the camera sees; keep track of objects over time; place information in space.

## Constraints
Lenovo ThinkPad X270, Core i7 7th gen, 8 GB RAM, NVMe, Windows, CPU-only assumption [Assumption]; one developer; low budget; privacy by default. See [RESOURCE_BUDGET.md](RESOURCE_BUDGET.md).

## Success criteria
- MVP: PRODUCT_SPEC acceptance criteria AC-1…AC-7 pass with evidence.
- Resource use measured on the reference laptop and within budget.
- No fabricated results anywhere; unsupported capabilities are reported honestly.
