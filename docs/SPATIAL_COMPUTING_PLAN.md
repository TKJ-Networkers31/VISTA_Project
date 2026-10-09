# Spatial Computing Plan

Status: **plan only; nothing implemented.** Governing decision: [ADR-0003](ADR/ADR-0003-spatial-capability-boundaries.md).

## Distinctions
| Concept | Meaning |
|---|---|
| Image pixel coords | 2D position in the original image |
| Normalized 2D coords | 0–1 relative 2D |
| Camera coords | 3D relative to camera; needs depth + intrinsics |
| World coords | 3D in a fixed frame; needs camera pose over time |
| Track identity | Same object across frames (2D tracking) |
| Spatial anchor | Persistent world-fixed reference; needs valid world coords and relocalization |

An OCR box or detection box is **not** a 3D position.

## Capability ladder (each rung needs validation evidence)
1. 2D detection/OCR (Phases 2–3).
2. 2D tracking with `track_id` (Phase 7).
3. Optional depth estimate (measured error documented) → camera-space point (Phase 7–8).
4. Camera pose from a real source (device AR framework or SLAM) → world-space (Phase 8).
5. Persistent anchors (Phase 8–9).
6. XR panels (Phase 9+).

## Reporting rule
The capability registry reports depth, pose, SLAM, anchors as `not_implemented` until validated, then `available`/`unavailable` per device. No simulated values.

## Candidate platforms (to evaluate, not decided)
ARCore/AR Foundation (Android), WebXR (browser), Unity, others by target device **[Open]**.

## Validation approach
Synthetic scenes with known ground truth for transform math; real-device manual protocol for tracking/anchoring; document error bounds.
