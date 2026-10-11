# Image understanding and hybrid routing (Phase 4)

**Status: implemented; verified with fakes and mocks only. NOT yet run against the real NVIDIA endpoint, in a real
browser, or on the X270.** Phase 3 exit conditions are still open (X270 measurements, weights license), so neither
Phase 3 nor Phase 4 is complete.

## 1. What it is
`POST /api/v1/understanding` answers a free-text question about ONE image using an **external** model
(`nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` on the hosted NVIDIA API by default). It is not OCR and returns no boxes.
Use OCR for exact text and detection for objects. No local provider exists for this capability, so `local_only` always rejects it.

| Piece | Path |
|---|---|
| Routing rules (pure) | `core/routing/policy.py`, `core/routing/budget.py` |
| NIM adapter | `core/providers/nim.py` |
| JPEG re-encode | `core/vision/encode.py` |
| Orchestration | `core/orchestration/understanding_service.py` |
| Contract `0.4-understanding` | `core/contracts/understanding.py` |
| HTTP | `apps/api/main.py` |
| Page | `apps/web/static/understanding.html`, `.js`, `.css` |
| Tests | `tests/test_understanding_api.py`, `test_nim_adapter.py`, `test_routing_policy.py`, `test_routing_budget.py`, `test_understanding_contract.py`, `test_understanding_ui.py`, `test_config_phase4.py`, `test_nim_real.py` (opt-in) |

## 2. Enable it (Windows, PowerShell)
1. Create a key on build.nvidia.com (never paste it into chat or commit it).
2. In your private `.env` (git-ignored) set:
```
VISTA_EXTERNAL_ENABLED=true
VISTA_NIM_API_KEY=<your key>
```
3. Start `python -m apps.api`, open `http://127.0.0.1:8000/static/understanding.html`. The provider pill must say "ready".
4. Choose a mode, tick the consent box, press Ask.

API example (question, mode and consent travel in the multipart body, so the access log never contains them):
```powershell
curl.exe -s -F "file=@C:\path\photo.jpg;type=image/jpeg" -F "question=What is on the table?" -F "mode=hybrid" -F "consent_external=true" http://127.0.0.1:8000/api/v1/understanding
```

## 3. Modes (proved by tests/test_understanding_api.py and tests/test_routing_policy.py)
| Mode | Behaviour for `image_understanding` |
|---|---|
| `local_only` | Rejected, 501 `CAPABILITY_UNSUPPORTED`. Provider never called. |
| `hybrid` | External only with consent; without it 403 `CONSENT_REQUIRED`. |
| `external_fallback` | No local provider exists, so external with consent (`FALLBACK_NO_LOCAL`); without consent 403. For capabilities that have a local provider it is local-first and an external retry needs consent AND an eligible failure (`unavailable`, `timeout`, `provider_internal`, `resource_limit`; never `invalid_input` or `cancelled`). |
Always required: `VISTA_EXTERNAL_ENABLED=true` (else 503 `EXTERNAL_DISABLED`) and a key (else 503 `EXTERNAL_NOT_CONFIGURED`).
Rejections happen before the image is decoded or sent. Default mode when a request names none: `VISTA_POLICY_DEFAULT`.

## 4. Response (`0.4-understanding`)
Fields: `request_id`, `status` (`succeeded`/`failed`/`unavailable`), `filename`, `image_width/height`, `question`, `answer`,
`route{mode,target,reason,provider,model,external_transmission}`, `processing_time_ms`, `warnings`, `error`.
`external_transmission=true` means an HTTP request carrying the image was attempted (also when it then failed).

## 5. Errors
| Code | HTTP | Meaning |
|---|---|---|
| CONSENT_REQUIRED | 403 | no per-request consent |
| CAPABILITY_UNSUPPORTED | 501 | `local_only` (no local provider) |
| EXTERNAL_DISABLED / EXTERNAL_NOT_CONFIGURED | 503 | master switch off / no key |
| INVALID_MODE / INVALID_PARAMETER | 400 | bad mode, question or boolean |
| EMPTY_FILE, CORRUPT_IMAGE, MISSING_FILE, UNSUPPORTED_FORMAT, IMAGE_* | 400/413/415 | same as OCR/detection |
| IMAGE_TOO_LARGE_FOR_PROVIDER | 413 | cannot be reduced below `VISTA_NIM_MAX_IMAGE_BYTES` |
| NIM_AUTH_FAILED / NIM_BAD_REQUEST / NIM_MALFORMED / NIM_EMPTY / NIM_SERVER_ERROR | 502 | provider-side problem |
| NIM_RATE_LIMITED, BUDGET_EXCEEDED | 429 | provider limit / local daily ceiling |
| NIM_TIMEOUT, TASK_TIMEOUT | 504 | per-attempt / whole-request timeout |
| NIM_NETWORK | 503 | unreachable |
| QUEUE_FULL, SERVER_SHUTTING_DOWN, CANCELLED | 429/503 | same as other services |

## 6. Privacy and security
- Sent externally ONLY: a re-encoded JPEG (no metadata) and the question, after the three conditions of ADR-0006 hold.
- The key lives in the server process only: not in responses, capabilities, logs, `repr(Settings)` or `Settings.public_dict()`.
  Tested with a provider that echoes the key back.
- Logs hold `request_id`, status, code, mode, target, sent flag, bytes, ms. Never the question, answer or image.
- https + host allow-list (`integrate.api.nvidia.com`), redirects refused, config validated at startup.
- The page sends nothing without the consent box ticked and stores nothing in the browser.
- `scripts/benchmark_ocr.py` must not dump the key: see the patch in section 9.
- NVIDIA's terms for the free endpoint and what they do with submitted images were NOT reviewed here. Read them before sending real photos.

## 6b. Timeouts (order matters)
`VISTA_EXTERNAL_TIMEOUT_SECONDS` (per HTTP attempt, 1..300) x (`VISTA_EXTERNAL_RETRY_MAX` + 1) must stay below
`VISTA_TASK_TIMEOUT_SECONDS` (whole request, shared with OCR/detection), which must stay below the 340 s limit of the page.
Suggested values for a slow provider: 150 / 1 retry / 320 / 340. Timeouts are never retried; only HTTP 429/503 are.

## 7. Limits and unverified items
- Live behaviour is unverified: response shape (`choices[0].message.content`), the inline image size limit (the 180 KB default
  is a conservative guess), whether `enable_thinking=false` is honoured, quotas, latency. Run `tests/test_nim_real.py` first.
- A reasoning model can spend all tokens thinking and return no text: reported as `NIM_EMPTY`.
- The daily ceiling counts HTTP attempts in memory; it resets at 00:00 UTC and on restart.
- A request already inside the HTTP call cannot be cancelled; the per-attempt timeout bounds it.
- Free text can be wrong and has no coordinates. Self-hosted NIM is not supported (URL allow-list).
- Colab and YOLO-World are NOT part of Phase 4 (separate experiments; nothing here depends on them).
- No routing-overhead or provider-latency figure was measured.

## 8. Tests
```powershell
python -m pytest -q                                   # no network, no key
python -m ruff check .
$env:VISTA_NIM_API_KEY = "<key>"; python -m pytest -q -m requires_network -s tests/test_nim_real.py   # ONE real request
```

## 9. Paste-in updates for existing files
- **scripts/benchmark_ocr.py** (do not write the key into reports): replace `"settings": dataclasses.asdict(settings)` with `"settings": settings.public_dict()`; keep `import dataclasses` only if still used elsewhere in the file (ruff F401 will tell).
- **docs/CONFIGURATION.md** table: add rows for `VISTA_POLICY_DEFAULT` (now read), `VISTA_EXTERNAL_ENABLED` (now read), `VISTA_EXTERNAL_RETRY_MAX` (0..3, default 1), `VISTA_EXTERNAL_TIMEOUT_SECONDS` (per attempt), `VISTA_EXTERNAL_DAILY_CALL_LIMIT`, `VISTA_NIM_API_KEY`, `VISTA_NIM_BASE_URL`, `VISTA_NIM_MODEL`, `VISTA_NIM_MAX_TOKENS`, `VISTA_NIM_ENABLE_THINKING`, `VISTA_NIM_MAX_IMAGE_BYTES`, `VISTA_UNDERSTANDING_MAX_SIDE`; note that `VISTA_EXTERNAL_API_KEY` is not read.
- **docs/API.md**: add `POST /api/v1/understanding` (multipart `file`, form `question`, `mode`, `consent_external`) and `GET /api/v1/understanding/capabilities`; link here.
- **README.md** capability table: `Image understanding (external, NVIDIA NIM, consent required) | Implemented in Phase 4; mock-tested; live NIM, browser and X270 validation pending (docs/UNDERSTANDING.md)`; add `[Understanding](docs/UNDERSTANDING.md)` to the index; keep the Phase 4 row honest (not complete).
- **CHANGELOG.md** `[Unreleased]` Added: routing policy, NIM adapter, `0.4-understanding` contract, `/api/v1/understanding`, page, tests, ADR-0006. Changed: `Settings` gained Phase 4 fields; `VISTA_POLICY_DEFAULT` and `VISTA_EXTERNAL_*` are now read.
- **docs/ADR/README.md** index: `- [ADR-0006: Hybrid routing and NVIDIA NIM](ADR-0006-hybrid-routing-and-nvidia-nim.md) (Proposed)`.
- **ai/DECISION_LOG.md** Proposals: `2026-10-10 (Phase 4): ADR-0006 (Proposed): pure routing policy; per-request consent + master switch + key; NVIDIA NIM hosted adapter for image_understanding only; contract 0.4-understanding. Colab and YOLO-World stay separate experiments. Open: NVIDIA terms for the free endpoint, live verification, daily ceiling value.`
- **docs/ROADMAP.md** Phase 4 status: `implemented in part; mock-tested only; live NIM test, X270 measurements and Phase 3 exit conditions open. Not complete.`
- **docs/FILE_TREE.md**: add `core/routing`, `core/providers/nim.py`, `core/vision/encode.py`, `apps/web/static/understanding.*`.
- **docs/RESOURCE_BUDGET.md**: nothing measured for Phase 4; keep "not measured".
