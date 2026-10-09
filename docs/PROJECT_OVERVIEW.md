# Project Overview

Labels used across docs: **[Decision]** agreed, **[Proposal]** recommended, **[Assumption]** to be tested, **[Open]** needs owner input.

## Vision
An AI assistant that sees through a phone camera or XR device, understands visual context, answers questions, and presents contextual information in 2D and later spatial panels. This is a long-term vision; none of it is implemented.

## Mission
Deliver the vision in small, testable milestones on low-cost hardware, keeping every capability honest about what it can and cannot do.

## Problem
Text extraction, object identification, and conversational explanation live in separate tools with inconsistent outputs and unclear privacy handling.

## Target users
- Primary: the project owner (developer/learner) validating the platform. [Assumption]
- Later: students, hobbyists, and people needing quick visual explanations or text extraction. [Assumption]

## Use cases
1. Upload an image and extract text with positions.
2. Upload an image and list detected objects with boxes.
3. View both overlaid on the image in a browser.
4. Point a phone camera at a scene for near-real-time overlays (Phase 6).
5. Ask spoken questions about a tracked target (Phase 7).
6. Place an information panel in space (Phases 8–9, only with valid pose/tracking).

## Constraints
- Hardware: Windows laptop, Core i7 7th gen, 8 GB RAM [Assumption: to be benchmarked].
- Low budget; pretrained models first.
- Privacy: no permanent raw image storage by default.
- Honesty: no fabricated results, coordinates, or benchmarks.

## Success indicators (MVP, Phase 5)
- Valid image → contract-compliant JSON with OCR and detection results or explicit capability statuses.
- Invalid/oversized input rejected with structured errors, never a crash.
- Contract and API tests pass in a real run.
- Measured latency and memory on target hardware are recorded (measured, not estimated).
