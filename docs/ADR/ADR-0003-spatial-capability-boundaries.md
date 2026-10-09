# ADR-0003: Spatial capability boundaries

- **Status:** Proposed (awaiting owner acceptance)

## Context
2D boxes are easily mistaken for spatial understanding. The long-term vision includes AR/MR but the MVP has no pose, depth, or tracking.

## Decision
Keep image-pixel, normalized, camera, and world coordinates as distinct, named spaces in contracts. Depth, pose, SLAM, anchors, and 3D overlays are reported `not_implemented` (then `available`/`unavailable`) through the capability registry and only become `available` after implementation **and** validation evidence. Fake or simulated 3D data is forbidden. See [SPATIAL_COMPUTING_PLAN.md](../SPATIAL_COMPUTING_PLAN.md).

## Alternatives considered
- Mock 3D coordinates for early UI demos: faster demos, but misleading and risks drift into false claims.
- Defer all spatial thinking: simpler now, but contracts could later need breaking changes.

## Consequences
+ Honest capability reporting; contracts ready for later phases.
− Early demos cannot show spatial overlays.

## Reconsider when
A target device with reliable pose/depth is chosen and validated.
