# VISTA Phase 4 report: Hybrid Provider Adapters and Image Understanding

Date of the evidence: 2026-10-10 / 2026-10-11. Machine: ThinkPad X270 (i7-7500U, 8 GB, Windows, CPU-only), Python 3.14.0.
Everything marked "observed" was run by the owner and pasted back; everything else is stated as such. No Git commit or push was made by the assistant.

## 1. Initial state
Phase 3 (detection) existed and passed its tests; its exit conditions (X270 measurements recorded in RESOURCE_BUDGET.md, weights license review) were
open. There was no routing policy, no external provider, no consent mechanism and no image-understanding capability. OCR (`0.2-ocr-mvp`) and
detection (`0.3-detection`) were stable and had to stay unchanged.

## 2. Files and why
New code: `core/routing/{__init__,policy,budget}.py` (routing rules as pure functions, daily call ceiling), `core/providers/nim.py` (NVIDIA NIM
adapter), `core/vision/encode.py` (bounded JPEG re-encode), `core/contracts/understanding.py` (contract `0.4-understanding`),
`core/orchestration/understanding_service.py`, `apps/web/static/understanding.{html,js,css}`, `scripts/diagnose_nim.py`,
`scripts/set_env_long_timeouts.ps1`.
Changed: `core/config.py` (Phase 4 settings, key hidden from `repr`, `public_dict()`), `core/contracts/__init__.py`,
`core/orchestration/__init__.py`, `apps/api/main.py` (new route, error mapping), `apps/api/__main__.py` (logs effective settings, never the key),
`apps/web/static/index.html` (one nav link), `scripts/benchmark_ocr.py` (settings dump no longer includes the key), `.env.example`.
Tests: `test_routing_policy`, `test_routing_budget`, `test_nim_adapter`, `test_understanding_contract`, `test_understanding_api`,
`test_understanding_ui`, `test_config_phase4`, `test_phase4_acceptance`, `test_nim_real` (opt-in), `tests/fakes_understanding.py`.
Docs: `docs/UNDERSTANDING.md`, `docs/ADR/ADR-0006-hybrid-routing-and-nvidia-nim.md`, `docs/PHASE4_MEASUREMENTS.md`, this report.
Not changed: OCR and detection endpoints, contracts and services.

## 3. Commands run (by the owner) and actual results
| Command | Result (observed) |
|---|---|
| `python -m ruff check .` | `All checks passed!` (an earlier run found one F401 in `scripts/benchmark_ocr.py`; fixed) |
| `pytest -q` (full) | `288 passed, 19 deselected, 1 warning in 24.91s` |
| `python -m pytest -q tests/test_phase4_acceptance.py` | `22 passed, 1 warning in 1.44s` |
| `node --test tests/js/realtime_core.test.js` | 24 tests, 24 pass, 0 fail |
| `python -m scripts.diagnose_nim --timeout 180 [--image ...]` | see section 6 |
| `python -m apps.api` + web page | see section 6 |
The 288 run and the 22 run were separate runs; a final single full run after all files are in place was not pasted (see gaps). The 19 deselected
tests are the opt-in ones (`requires_model`, `requires_network`).

## 4. Behaviour proved by tests (counting transport: the number of HTTP requests reaching the provider is asserted)
| Case | Expected | Evidence |
|---|---|---|
| `local_only`, consent true or false, or default mode | 501 `CAPABILITY_UNSUPPORTED`, 0 requests | `test_phase4_acceptance` (passed) |
| `hybrid` / `external_fallback` without consent | 403 `CONSENT_REQUIRED`, 0 requests | same |
| master switch off, or no key | 503, 0 requests | same |
| `hybrid` / `external_fallback` with consent | exactly 1 request, JPEG data URI, key only in the header | same |
| corrupt image with consent | 400, no request | same |
| 401, 403, 429, 500, 503, timeout, connection reset, malformed JSON, empty `choices`, empty text | distinct codes and HTTP statuses, no key in the response | same + `test_nim_adapter` |
| retries and budget | retries only after 429/503 and at most `VISTA_EXTERNAL_RETRY_MAX` (0..3); timeouts never retried; daily ceiling stops calls | `test_nim_adapter`, `test_routing_budget` |
| key, question, answer, image data in logs | absent | `test_phase4_acceptance`, `test_understanding_api` |
| OCR and detection | never touch the provider; shapes unchanged | `test_phase4_acceptance`, shape-freeze tests, full suite |
| `local_only` with the real default transport and a network guard | no connection attempted | `test_phase4_acceptance` |
Unit-level only: `may_fallback` (fallback after a local failure applies only to `unavailable`, `timeout`, `provider_internal`,
`resource_limit`, never `invalid_input` or `cancelled`) is tested as a function. No local capability has an external provider, so this path is
not wired into OCR or detection (see gaps).

## 5. How to enable NVIDIA NIM
In the private `.env`: `VISTA_EXTERNAL_ENABLED=true`, `VISTA_NIM_API_KEY=<key>`, optionally `VISTA_POLICY_DEFAULT=hybrid`. Suggested slow-provider
timeouts: `VISTA_EXTERNAL_TIMEOUT_SECONDS=150`, `VISTA_EXTERNAL_RETRY_MAX=1` (or 2, see section 6), `VISTA_TASK_TIMEOUT_SECONDS=320`. Restart the
server; the first log line (`vista.config ...`) shows the values actually used. Page: `/static/understanding.html`. Each request also needs the
consent box (form field `consent_external=true`). Details: `docs/UNDERSTANDING.md`.

## 6. Measurements (observed; one run per row, no distribution)
Full tables: `docs/PHASE4_MEASUREMENTS.md`. Summary:
- Server `ms` for successful web requests: 4619.8 ms (83,574 B uploaded) and 27203.3 ms (100,387 B uploaded). The second would likely have timed out under the old 30 s setting.
- Two earlier requests (137,275 B JPEG) hit `NIM_TIMEOUT` at the old 30 s limit (32637.7 ms and 30445.9 ms).
- `diagnose_nim` on the owner's PNG re-encoded as JPEG: 86,815 B in 2.1 s, 57,099 B in 4.4 s, 29,617 B in 1.8 s (provider call only).
- The provider answered HTTP 503 `ResourceExhausted: Worker local total request limit reached (16/16)` at least once; short failures with synthetic images
  (1.6 to 3.5 s) are consistent with that, but two of them were not shown with their HTTP status.
- The provider accepted an inline image of 137,275 B (about 183,000 base64 characters).
- Answer quality: the topology answer for the lab diagram contained invented details (an interface count, a traffic direction, a "tablet"), and for a
  math-lesson image three sizes gave three different answers. Free text from the model must be checked against the image.
- Not measured: local re-encode time, routing overhead, RSS during an external request, `enable_thinking=false` behaviour, quota, repeated-request
  behaviour, any median or p95.

## 7. Acceptance criteria
| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Provider contract and routing integrated | PASS | policy, adapter, service, route, tests; live requests |
| 2 | NIM adapter tested with mocks; live if credentials | PASS | `test_nim_adapter` and acceptance tests; live: 2 web requests + `diagnose_nim` |
| 3 | `local_only` sends nothing | PASS | acceptance tests with a request counter and a network guard |
| 4 | Consent and fallback policy proved by tests | PASS for the policy as implemented | consent: end to end. Fallback: function-level and `external_fallback` on the one capability that has no local provider |
| 5 | Provider errors, timeouts, retries bounded | PASS | tests in section 4 |
| 6 | No OCR or detection regression | PASS | full suite 288 passed, shape-freeze tests |
| 7 | Old API contracts compatible | PASS | `0.2-ocr-mvp` and `0.3-detection` unchanged, tests passed |
| 8 | Tests and lint pass with real output | PASS | section 3 |
| 9 | Docs for config, privacy, capabilities, limits updated | NOT VERIFIED by the assistant | the docs were delivered; the paste-in edits to README, CHANGELOG, CONFIGURATION, API, ROADMAP, DECISION_LOG, ADR index, FILE_TREE and RESOURCE_BUDGET cannot be seen from here (check below) |
| 10 | Blockers, open decisions, untested items recorded | PASS | sections 8 and 9 |

## 8. Remaining gaps (explicit)
1. Criterion 9: confirm the doc updates are in the repository, in particular a Phase 4 section in `RESOURCE_BUDGET.md` (text is at the end of `docs/PHASE4_MEASUREMENTS.md`).
2. External fallback for OCR and detection is not implemented. The only external provider supports `image_understanding`; no external OCR or detection provider exists. Decision recorded here: treat it as not applicable to Phase 4 unless the owner adds such a provider.
3. NVIDIA's terms for the free endpoint, and how submitted images are handled, were not reviewed.
4. No final single full-suite run after every file was in place was pasted.
5. The 503 "provider is full" case shows up as `NIM_SERVER_ERROR` ("The external provider failed."). A dedicated retryable code would be clearer; not implemented.
6. Colab and YOLO-World are not part of Phase 4. Nothing depends on them; Colab has no runtime integration by decision (ADR-0006).
7. Phase 3 is still NOT COMPLETE: weights/COCO license review is open, and the X270 detection benchmark results must be recorded in `RESOURCE_BUDGET.md`.

## 9. Decision
**Phase 4: COMPLETE for criteria 1 to 8 and 10; criterion 9 is unconfirmed.** Phase 4 may be declared COMPLETE once the verification command below shows the
doc updates in place; if any file is missing its entry, Phase 4 stays NOT COMPLETE until the text from `docs/UNDERSTANDING.md` section 9 is applied.
Phase 3 stays NOT COMPLETE. Phase 5 has not been started.
```powershell
Test-Path docs\UNDERSTANDING.md, docs\PHASE4_MEASUREMENTS.md, docs\ADR\ADR-0006-hybrid-routing-and-nvidia-nim.md
Select-String -Path README.md,CHANGELOG.md,docs\ROADMAP.md,docs\CONFIGURATION.md,docs\API.md,docs\FILE_TREE.md,docs\RESOURCE_BUDGET.md,docs\ADR\README.md,ai\DECISION_LOG.md -Pattern "understanding|ADR-0006|NIM" | Group-Object Path | Select-Object Count,Name
python -m pytest -q
```
All three Test-Path results must be True, every listed file must appear in the grouped output, and the final `pytest -q` count is the number to record.

## 10. Next steps (roadmap)
Close criterion 9 and the Phase 3 exit conditions; then Phase 5 (live camera with a bounded frame queue, drop-oldest policy, soak test) per `docs/ROADMAP.md`.
Optional hardening: a dedicated `NIM_OVERLOADED` error for provider 503, and `VISTA_EXTERNAL_RETRY_MAX=2` while the shared endpoint is saturated.
