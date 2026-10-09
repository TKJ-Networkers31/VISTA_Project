# Data Contracts

Schema version **`0.2`** (conceptual **[Proposal]**; becomes real when `core/contracts` is implemented in Phase 1–2). Breaking changes bump the version and require an ADR.

## Conventions
- UTF-8 JSON, snake_case keys. Timestamps UTC ISO 8601. Durations in ms.
- Confidence: float 0–1 or `null` if the provider gives none. Never invented.
- All examples are **illustrative**, not real outputs.

## Coordinate spaces (never conflate)
| Space | Definition | Status |
|---|---|---|
| `image_pixels` | Original image pixels, origin top-left, x right, y down | Used (MVP basis) |
| `image_normalized` | 2D, 0–1 relative to image width/height | Optional derived form |
| `camera_space` | 3D metric coordinates relative to the camera | Not implemented |
| `world_space` | 3D coordinates in a tracked world frame | Not implemented |

`bbox2d` = `[x_min, y_min, x_max, y_max]` in the space named by `coordinate_space`. A 2D box is never a 3D position. Tracked object identity (`track_id`) and persistent spatial anchors are separate concepts and appear only in later phases.

## Result envelope (all responses)
| Field | Type | Notes |
|---|---|---|
| `schema_version` | string | `"0.2"` |
| `request_id` | string | unique per request |
| `status` | enum | `succeeded`, `partial`, `failed`, `unavailable`, `not_implemented` |
| `result` | object or null | payload; shape depends on endpoint |
| `errors` | array | provider/request errors (see Provider error) |
| `timing_ms` | object or null | when measurable |
| `capabilities` | object | per-capability status and provider metadata |

### Capability status
`{ "status": "available|unavailable|not_implemented|disabled|failed", "provider": {"id","model","locality":"local|external"} | null, "reason": string|null }`

## Image analysis request
`POST /v1/analyze` multipart: `file` (image), optional `options` JSON: `{ "capabilities": ["ocr"], "policy": "local_only" }`. Policy values: `local_only`, `hybrid`, `external_fallback`. External use requires configured consent ([API_PROVIDER_POLICY.md](API_PROVIDER_POLICY.md)).

## Example: OCR success
```json
{
  "schema_version": "0.2",
  "request_id": "req_example_001",
  "status": "succeeded",
  "result": {
    "image": { "width": 1280, "height": 720, "coordinate_space": "image_pixels" },
    "ocr": {
      "items": [
        { "text": "EXIT", "confidence": 0.97, "bbox2d": [100, 50, 220, 90] },
        { "text": "Sample", "confidence": null, "bbox2d": [100, 100, 260, 140] }
      ]
    },
    "detection": null,
    "spatial": { "status": "not_implemented" }
  },
  "errors": [],
  "timing_ms": { "decode": 12, "ocr": 480, "total": 520 },
  "capabilities": {
    "ocr": { "status": "available", "provider": { "id": "example-local-ocr", "model": "example", "locality": "local" }, "reason": null },
    "detection": { "status": "not_implemented", "provider": null, "reason": "planned for Phase 3" },
    "spatial": { "status": "not_implemented", "provider": null, "reason": "no pose, tracking, or depth source" }
  }
}
```

## OCR result
`items[]`: `text` (string), `confidence` (number|null), `bbox2d` (4 numbers). Optional `polygon` (list of `[x,y]`) if the provider returns quads.

## Object detection result (Phase 3)
`items[]`: `label` (string), `confidence` (number|null), `bbox2d` (4 numbers), optional `track_id` (string|null; Phase 7). Same normalization as OCR.

## Provider error
```json
{
  "category": "timeout",
  "code": "PROVIDER_TIMEOUT",
  "message": "Provider did not respond within the configured timeout.",
  "capability": "ocr",
  "provider_id": "example-local-ocr",
  "retryable": true,
  "details": { "timeout_ms": 30000 }
}
```
Categories: `invalid_input`, `unavailable`, `timeout`, `cancelled`, `quota_exceeded`, `auth_failed`, `network`, `provider_internal`, `resource_limit`, `not_implemented`.

## Error response example
```json
{
  "schema_version": "0.2",
  "request_id": "req_example_002",
  "status": "failed",
  "result": null,
  "errors": [
    { "category": "invalid_input", "code": "IMAGE_TOO_LARGE", "message": "Image exceeds the configured limit.", "capability": null, "provider_id": null, "retryable": false, "details": { "limit_bytes": 10485760 } }
  ],
  "timing_ms": null,
  "capabilities": {}
}
```

## Task status
```json
{
  "schema_version": "0.2",
  "request_id": "req_example_003",
  "status": "succeeded",
  "result": { "task_id": "task_example_1", "state": "running", "queued_at": "2026-01-01T00:00:00Z", "started_at": "2026-01-01T00:00:01Z", "finished_at": null },
  "errors": [],
  "timing_ms": null,
  "capabilities": {}
}
```
States: `queued`, `running`, `succeeded`, `failed`, `timed_out`, `cancelled`, `rejected`. (`status` in the envelope describes the *request to read the task*; `result.state` describes the task.)

## Voice request and response (Phase 6, planned)
Request: `{ "session_id", "audio_ref" | "text", "target": {"track_id"|null}, "policy" }`. Response `result`: `{ "transcript", "intent", "answer_text", "tts_available": bool, "grounding": [ {"source":"ocr|detection","ref"} ] }`. Audio is never retained by default.

## Spatial result
MVP and until Phase 8 is validated:
```json
{ "status": "not_implemented", "coordinate_space": null, "position": null, "reason": "no pose, tracking, or depth source" }
```
When implemented, `position` must declare `camera_space` or `world_space` and the transform source. Fake 3D coordinates are forbidden.

## Validation
JSON Schema files will live in `core/contracts/` and drive contract tests.
