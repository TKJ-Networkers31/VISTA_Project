# Post-MVP Validation Audit

Scope: audit of the MVP patch (`VISTA_mvp_patch.zip`, 44 files) and its tests, preparation for Windows / ThinkPad X270 validation.
The previous report was **not** treated as evidence: tests, lint, benchmark and probes were re-run in this stage.
Date of runs: 2026-10-09, Linux sandbox (1 logical CPU). **Nothing was run on Windows or on the X270.**

## 1. Evidence matrix
### Actually executed (Linux only)
| Check | Environment | Result |
|---|---|---|
| `ruff check .` | py3.11.17, py3.12.3 (onnxruntime 1.31.0) and py3.12.3 (onnxruntime 1.30.0) | all checks passed |
| `pytest -q` (mock engine, offline) | the same three environments | 45 passed, 9 deselected (each) |
| `pytest -m requires_model` (REAL rapidocr engine, non-loopback network blocked) | the same three | 9 passed (each) |
| `scripts.benchmark_ocr --runs 5 --warmup 2` | py3.11.17, py3.12.3 (ort 1.31.0) | completed, 30 ok / 0 failed each (numbers in RESOURCE_BUDGET.md) |
| `scripts.probe_server` (5 probes, real server + real engine) | py3.11.17, py3.12.3 | all PASS (details in section 3) |
| `pip install --dry-run --platform win_amd64 ...` | cp311, cp312, cp313 | metadata resolution only (see WINDOWS_VALIDATION.md) |
| PowerShell 7.5.4 (Linux) parse of `validate_windows.ps1`; functional test of its `Invoke-Step` helper | pwsh 7.5.4 | 0 syntax errors; PASS/FAIL/exit-code handling behaved as intended |
Environments 1-2 used the *same package versions pip resolves for Windows x64* (constraints files) but Linux wheels.

### Only checked statically (not executed)
- `scripts/validate_windows.ps1` as a whole (never run end to end; Windows PowerShell 5.1 never used; kept ASCII-only for 5.1).
- Windows shutdown path in `probe_server.py` (`CTRL_BREAK_EVENT`), Windows temp-dir env handling (`TEMP`/`TMP`).
- Extra ruff rules (S, ASYNC, BLE, PERF): only BLE001 (blind `except Exception`) fired; intentional at error boundaries (messages are sanitized, only the exception *type* is logged).
- Package compatibility claims: metadata only.

### Requires Windows / the X270
Install of the Windows wheels, onnxruntime DLL loading (VC++ runtime question), real-engine tests, latency / RAM / CPU numbers, UI in a real browser,
Ctrl+C behavior, firewall prompt, outbound-connection check, real-photo quality. See checklist M-1..M-13 in WINDOWS_VALIDATION.md.

## 2. Findings
| ID | Finding | Status |
|---|---|---|
| F-1 | **Patch defect:** the `.env.example` in the first patch contained only the 2 OCR lines; copying it would have replaced the real file. | Fixed: file now contains the full original content plus the OCR lines. Compare with your repo copy before overwriting. |
| F-2 | No shutdown handling: executor never stopped, running tasks not signalled, new work accepted during shutdown. | Fixed: FastAPI lifespan calls `OCRService.shutdown()` (stop admitting, set cancel flags, `SERVER_SHUTTING_DOWN`). Tested (3 tests) and probed (exit in 1.7-1.9 s with a request in flight, which still completed with 200). |
| F-3 | Admission slot could leak if the executor refused a job. | Fixed + tested. |
| F-4 | `.env` saved with a UTF-8 BOM (common with Windows editors) would corrupt the first key. | Fixed (`utf-8-sig`) + tested. |
| F-5 | Timeout cannot interrupt a running engine call; the client gets 504 but the thread keeps the slot until it finishes. | Not changed (design limit, documented). Probe: 8 requests with a 1 s timeout all returned `TASK_TIMEOUT`; queued ones were cancelled before OCR and the queue drained to 0 in 1.3 s. Because OCR of the large fixture takes >1 s on this 1-vCPU sandbox, "success after a timeout" was not exercised. |
| F-6 | **Open:** `import onnxruntime` writes a 51-byte `.ses` file (a timestamp and a UUID) to the temp dir; onnxruntime 1.30.0 also created an empty `mat-debug-<pid>.log`. Purpose not determined. Written by native code (not visible to Python audit hooks). Python-level socket recording during import+load+OCR showed no connection or DNS attempts, but native-code network use cannot be observed this way. | Open. Verify on the X270 with an outbound block / connection monitor (M-9). Do not claim "no telemetry". |
| F-7 | My own first real-engine geometry assertion was wrong (expected x > 1600 on a 3000 px image whose text spans ~1444 px). The test failed; it was **replaced** by a ground-truth IoU check (best IoU 0.85-0.93) instead of loosening a number. | Fixed |
| F-8 | Response shape deviates from `DATA_CONTRACTS.md`. | Proposed: ADR-0004. Not changed. |
| F-9 | Starlette spools multipart parts >1 MB to the OS temp dir while parsing. | Bounded by the `Content-Length` gate (413 before parsing; chunked bodies rejected with 411). Verified: test with a 1.47 MB noisy PNG + probe: no files created by uploads. |
| F-10 | Huge-dimension PNGs (7000², 12000², 20000² bilevel, <1 MB on disk) | Rejected from the header with `IMAGE_DIMENSIONS_EXCEEDED` before decode; engine never reached (tested). |
| F-11 | First OCR after start is slower than warm (Linux: ~1.7-3.0 s vs ~1 s) | Observed; the benchmark records it separately. |
| F-12 | `/docs` (OpenAPI UI) is enabled. Fine on `127.0.0.1`; disable or protect before any LAN exposure. | Not changed |
| F-13 | Not implemented: idle model unload; memory-floor stop policy; RAM for the largest allowed image (20 MP) not measured. | Open |
| F-14 | Windows asyncio (Proactor loop) behavior of the service/thread-pool design is untested. | Open (M-2/M-11) |

## 3. Probe results (Linux, real engine; `scripts.probe_server`)
| Probe | Result |
|---|---|
| backpressure (workers 1, queue 2, 10 concurrent requests) | 3x 200, 7x 429; drained to 0; server peak RSS 508-514 MB |
| timeout + drain (timeout 1 s, 8 requests) | 8x 504 `TASK_TIMEOUT`, drained in 1.3 s; request after drain returned a structured 504 (see F-5) |
| temp files (3 uploads of 1.47 MB) | 3x 200; files created by uploads: none (library file `.ses` existed before uploads) |
| limits | declared 500 MB body: 413 without reading it; chunked: 411; server stayed healthy |
| shutdown (SIGINT with a request in flight) | exit code 0 in 1.7 s (3.11) / 1.9 s (3.12); the in-flight request returned 200 |

## 4. Open risks
Windows install/runtime of onnxruntime (VC++ runtime, CPU support) unverified; F-6 telemetry/network question; X270 latency and RAM unknown
(Linux numbers are not a proxy); first-run model/page-cache slowness; accuracy on real photos and Indonesian text unmeasured;
contract drift (ADR-0004); timeouts do not stop running inference (F-5); `rapidocr-onnxruntime` 1.4.4 does not support Python 3.13+.

## 5. Files changed or added in this stage (relative to the MVP patch)
Changed: `core/orchestration/ocr_service.py`, `apps/api/main.py`, `core/config.py`, `.env.example` (now complete), `requirements-dev.txt` (+psutil),
`docs/API.md`, `docs/OCR.md`, `docs/MVP_DOC_UPDATES.md`.
Added: `scripts/{__init__,benchmark_ocr,make_fixtures,probe_server}.py`, `scripts/validate_windows.ps1`, `constraints/windows-cp311.txt`, `constraints/windows-cp312.txt`,
`tests/{netguard,test_real_engine,test_validation_prep}.py`, `tests/fixtures/` (6 PNG + manifest.json), `docs/{WINDOWS_VALIDATION,VALIDATION_AUDIT,RESOURCE_BUDGET}.md`,
`docs/ADR/ADR-0004-ocr-response-contract.md`, `results/` (Linux benchmark/probe JSON, git-ignored). `docs/RESOURCE_BUDGET.md` is the original text plus a "Measured results" section.
No file was deleted; the API contract was not changed; no commit or push.
