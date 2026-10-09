# Paste-in updates for existing docs (Implementation Prompt 01)

**README.md** – status: "Phase 1–2 MVP implemented: upload image → local OCR → structured result + web UI. Detection/camera/voice/spatial: not implemented." Quick start:
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
python -m apps.api        # open http://127.0.0.1:8000
python -m pytest
```
**WINDOWS_SETUP.md** – step 3: `python -m pip install -r requirements-dev.txt` now installs runtime deps incl. rapidocr-onnxruntime; step 6: `python -m apps.api`. Windows run is NOT yet verified (built/tested on Linux). If onnxruntime has no wheel for your Python, use 3.11.
**CONFIGURATION.md** – add `VISTA_OCR_ENGINE` (`rapidocr`) and `VISTA_OCR_MAX_SIDE` (`1600`). Unused so far: `VISTA_MODEL_IDLE_UNLOAD_SECONDS`, `VISTA_POLICY_DEFAULT`, `VISTA_EXTERNAL_*`, `VISTA_RETAIN_RAW_IMAGES`, `VISTA_TEMP_DIR`, `VISTA_LOG_REDACT`, `VISTA_MAX_RESIDENT_MODELS`.
**ARCHITECTURE.md** – flow: `apps/api (Content-Length gate, multipart) → core/orchestration.OCRService (bounded admission, timeout) → core/vision.validation → core/ocr (provider, normalize) → core/contracts.OCRResponse`. Settings live in `core/config.py`.
**RESOURCE_BUDGET.md** – add the measured figures from docs/OCR.md, labeled sandbox-only.
**TEST_STRATEGY.md** – `python -m pytest` (29 tests, mock engine); real engine: `python -m pytest -m requires_model -s`.
**CHANGELOG.md / directory READMEs / FILE_TREE.md** – mark api, web, contracts, orchestration, providers, vision, ocr as implemented; storage/voice/spatial unchanged.

## Added in the validation stage
- **docs/ADR/README.md** index: add `- [ADR-0004: OCR response contract](ADR-0004-ocr-response-contract.md)` (Proposed).
- **ai/DECISION_LOG.md**: add under Proposals: "ADR-0004 (Proposed): reconcile OCR MVP response `0.2-ocr-mvp` with DATA_CONTRACTS 0.2; recommendation: staged (option C)". Do not mark Accepted until the owner decides.
- **docs/FILE_TREE.md**: add `scripts/` (benchmark_ocr, probe_server, make_fixtures, validate_windows.ps1), `constraints/`, `tests/fixtures/`, `results/` (git-ignored).
- **scripts/README.md**: status "implemented: benchmark, probes, fixture generator, Windows validation; none run heavy inference unless invoked".
- **docs/TEST_STRATEGY.md**: real-engine tests are `-m requires_model` and run with non-loopback network blocked; fixtures are synthetic and committed; the contract-shape characterization test.
- **docs/WINDOWS_SETUP.md**: link to WINDOWS_VALIDATION.md and use `-c constraints\windows-cp311.txt` for installs.
- Replace the earlier statement that the MVP "was tested on Linux" with the evidence matrix in docs/VALIDATION_AUDIT.md.
