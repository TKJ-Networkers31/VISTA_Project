# API (OCR MVP + detection)

Run: `python -m apps.api` (binds `127.0.0.1:8000`). Interactive docs: `/docs`. Web UI: `/`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Service status, OCR capability, queue depth |
| GET | `/api/v1/ocr/capabilities` | Engine, availability, limits, queue |
| POST | `/api/v1/ocr` | multipart field `file` (JPEG/PNG/WebP); optional query `include_raw=true` |
| POST | `/api/v1/detection` | multipart field `file`; optional `confidence`, `max_detections`; see [DETECTION.md](DETECTION.md) |
| GET | `/api/v1/detection/capabilities` | Detection status (`available`/`unavailable`/`disabled`), model, parameters, limits |
| GET | `/api/v1/capabilities` | OCR, detection and `spatial` (`not_implemented`) with `implemented` flags; resident models |

Requests to `POST /api/v1/ocr` and `POST /api/v1/detection` must carry `Content-Length` (411 otherwise) and are rejected with 413 before parsing if larger than `VISTA_MAX_UPLOAD_BYTES` + 64 KiB.

## Response (`schema_version` = `0.2-ocr-mvp`)
| Field | Type | Notes |
|---|---|---|
| `request_id` | string | `req_<12 hex>` |
| `status` | `succeeded` / `failed` / `unavailable` | |
| `filename` | string\|null | basename only, sanitized, never used as a path |
| `image_width`, `image_height` | int\|null | after EXIF orientation |
| `coordinate_space` | `"image_pixels"` | original pixels, origin top-left |
| `detected_text` | string | lines joined with `\n` in reading order |
| `blocks[]` | array | `text`, `bbox2d` `[x1,y1,x2,y2]`\|null, `polygon`\|null, `confidence` 0–1\|null, `line_index` |
| `processing_time_ms` | number\|null | decode + OCR + normalize |
| `engine` | `{id, version, locality}` | |
| `warnings` | string[] | e.g. downscaled, no text found |
| `error` | `{category, code, message, retryable, details}`\|null | |
| `raw` | array\|null | raw engine output, only with `include_raw=true` |

`bbox2d`, `polygon` and `confidence` are `null` when the engine does not supply them; values are never invented.

## Errors
| Code | HTTP | Meaning |
|---|---|---|
| EMPTY_FILE / CORRUPT_IMAGE / MISSING_FILE | 400 | bad input |
| LENGTH_REQUIRED | 411 | no Content-Length |
| IMAGE_TOO_LARGE / IMAGE_DIMENSIONS_EXCEEDED | 413 | bytes, side or pixel limit |
| UNSUPPORTED_FORMAT | 415 | not JPEG/PNG/WebP (verified by decoding) |
| QUEUE_FULL | 429 | bounded queue full (`resource_limit`, retryable) |
| ENGINE_UNAVAILABLE / ENGINE_LOAD_FAILED | 503 | status `unavailable` |
| MODEL_BUSY | 429 | another model holds the residency slot (OCR and detection share it); retryable |
| ENGINE_FAILED / INTERNAL_ERROR | 500 | no internal text is exposed |
| TASK_TIMEOUT | 504 | `VISTA_TASK_TIMEOUT_SECONDS` exceeded; the engine call cannot be interrupted, the slot is freed when it really finishes |
| CANCELLED | 503 | task stopped before OCR (timeout while queued, or server shutdown) |
| SERVER_SHUTTING_DOWN | 503 | new work refused during shutdown (`unavailable`, retryable) |

Note: this response shape follows Implementation Prompt 01 and differs from the conceptual envelope in `DATA_CONTRACTS.md` (0.2). Reconcile in an ADR/contract update.

## Detection
The detection endpoint has its own response contract (`0.3-detection`: `detections[]` with `class_id`, `label`, `confidence`, `bbox2d`), error codes (`DETECTOR_*`, `DETECTION_DISABLED`, `INVALID_PARAMETER`) and example. Full reference: [DETECTION.md](DETECTION.md). The OCR response above is unchanged.
