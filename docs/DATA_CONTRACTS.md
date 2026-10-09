# Data Contracts

Schema version: **`0.1`** (conceptual, **[Proposal]** until implemented in Phase 1–2). Breaking changes bump the version and are recorded in an ADR.

## Conventions
- Coordinates default to `coordinate_space: "image_pixels"`: origin top-left of the **original** image, x right, y down, unit = pixel.
- `bbox` = `[x_min, y_min, x_max, y_max]` in that space.
- Confidence is a float 0–1 or `null` when the provider supplies none. It is never invented.
- Timestamps are UTC ISO 8601. Durations are milliseconds.
- OCR and detection items share the same normalized base: `{ id, bbox, confidence }` plus `text` or `label`.

## Coordinate spaces (never conflate)
| Space | Meaning | MVP |
|---|---|---|
| `image_pixels` | 2D pixels of original image | Used |
| `camera_space` | 3D metric coords relative to camera | Not available |
| `world_space` | 3D coords in a tracked world frame | Not available |

## Capability status
`capabilities.<name>.status` ∈ `ok`, `failed`, `skipped`, `unavailable`. `spatial` is `unavailable` in MVP with a `reason`.

## Analysis response
```json
{
  "schema_version": "0.1",
  "request_id": "req_01HZXAMPLE",
  "created_at": "2026-01-01T00:00:00Z",
  "image": { "width": 1280, "height": 720, "coordinate_space": "image_pixels" },
  "capabilities": {
    "ocr": { "status": "ok", "provider": "example-ocr", "error": null },
    "detection": { "status": "ok", "provider": "example-detector", "error": null },
    "spatial": { "status": "unavailable", "provider": null, "reason": "no pose, tracking, or depth source", "error": null }
  },
  "ocr": [
    { "id": "ocr_0", "text": "EXIT", "confidence": 0.97, "bbox": [100, 50, 220, 90] },
    { "id": "ocr_1", "text": "Sample", "confidence": null, "bbox": [100, 100, 260, 140] }
  ],
  "detections": [
    { "id": "det_0", "label": "chair", "confidence": 0.81, "bbox": [400, 200, 640, 700] }
  ],
  "spatial": null,
  "timings_ms": { "decode": 12, "ocr": 480, "detection": 210, "total": 720 },
  "warnings": []
}
```
All values above are **illustrative examples**, not real outputs.

## Error response
```json
{
  "schema_version": "0.1",
  "request_id": "req_01HZXAMPLE",
  "error": {
    "code": "IMAGE_TOO_LARGE",
    "message": "Image exceeds the configured limit.",
    "details": { "limit_bytes": 10485760 }
  }
}
```

### Error codes (proposed)
`INVALID_REQUEST`, `UNSUPPORTED_MEDIA_TYPE`, `IMAGE_TOO_LARGE`, `IMAGE_PIXELS_EXCEEDED`, `IMAGE_DECODE_FAILED`, `CAPABILITY_FAILED`, `INTERNAL_ERROR`.

## Validation
A JSON Schema file will be added under `core/contracts/` in Phase 1–2 and used by contract tests.
