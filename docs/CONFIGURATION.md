# Configuration

Configuration comes from environment variables (loaded from `.env` locally) with documented defaults. All defaults are **provisional**. Secrets live only in `.env` or the OS environment, never in committed files or logs. `configs/` holds non-secret structured config (e.g. provider routing) when needed.

| Variable | Default | Purpose |
|---|---|---|
| `VISTA_HOST` / `VISTA_PORT` | `127.0.0.1` / `8000` | Bind address; LAN is opt-in |
| `VISTA_LOG_LEVEL` | `INFO` | Logging |
| `VISTA_MAX_UPLOAD_BYTES` | `10485760` | Upload size cap |
| `VISTA_MAX_IMAGE_SIDE` | `6000` | Max width/height |
| `VISTA_MAX_IMAGE_PIXELS` | `20000000` | Max total pixels |
| `VISTA_ALLOWED_MIME` | jpeg,png,webp | Allowed types |
| `VISTA_WORKER_CONCURRENCY` | `1` | Workers |
| `VISTA_QUEUE_MAX_SIZE` | `4` | Bounded queue |
| `VISTA_TASK_TIMEOUT_SECONDS` | `60` | Task timeout |
| `VISTA_MAX_RESIDENT_MODELS` | `1` | Heavy models in RAM |
| `VISTA_MODEL_IDLE_UNLOAD_SECONDS` | `120` | Idle unload |
| `VISTA_POLICY_DEFAULT` | `local_only` | `local_only`, `hybrid`, `external_fallback` |
| `VISTA_EXTERNAL_ENABLED` | `false` | Master switch for external services |
| `VISTA_EXTERNAL_RETRY_MAX` | `2` | Retry cap |
| `VISTA_EXTERNAL_TIMEOUT_SECONDS` | `30` | External call timeout |
| `VISTA_EXTERNAL_API_KEY` | empty | Secret; private `.env` only |
| `VISTA_RETAIN_RAW_IMAGES` | `false` | Raw image retention |
| `VISTA_TEMP_DIR` | `./tmp` | Temp files |
| `VISTA_LOG_REDACT` | `true` | Redact content/secrets in logs |

Rules: invalid config fails fast at startup with a clear message (without printing secret values); config is validated by a typed settings object (Phase 1); each new variable is added here and in `.env.example` in the same change.
