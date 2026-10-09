# Windows Validation Guide (ThinkPad X270, Python 3.11 / 3.12)

**Status: prepared, NOT yet run on Windows.** Everything below was built and tested only on Linux
(see [VALIDATION_AUDIT.md](VALIDATION_AUDIT.md)). VISTA is not "ready on Windows" until the checklist at the end passes on the X270.

## 1. What package metadata says (verified 2026-10-09, not runtime-tested on Windows)
Method: `pip install --dry-run --only-binary=:all: --platform win_amd64 --python-version <v> --abi cp<v> -r requirements-dev.txt --report ...`
against PyPI. A successful resolution means *wheels exist for win_amd64*; it does not prove the software runs.

| Item | Python 3.11 (cp311) | Python 3.12 (cp312) | Python 3.13 |
|---|---|---|---|
| rapidocr-onnxruntime | 1.4.4 (pure-Python wheel; `requires_python <3.13`) | 1.4.4 | **1.4.4 is excluded**; pip silently falls back to old 1.2.3. Do not use 3.13. |
| onnxruntime | 1.31.0 win_amd64 wheel | 1.31.0 win_amd64 wheel | wheel exists, but see above |
| numpy | 2.4.6 | 2.5.3 | 2.5.3 |
| opencv-python / pillow / pyclipper / shapely / pyyaml | win_amd64 wheels resolved (opencv 5.0.0.93, pillow 12.3.0, pyclipper 1.4.0, shapely 2.2.0) | same | same |
| psutil, pytest, ruff, httpx | win_amd64 wheels resolved | same | - |

Resolved pin sets: `constraints/windows-cp311.txt`, `constraints/windows-cp312.txt` (candidates, not Windows-tested).
**Tested on Linux with those exact versions:** Python 3.11.17 + onnxruntime 1.31.0 + numpy 2.4.6, and Python 3.12.3 + onnxruntime 1.31.0 + numpy 2.5.3
(tests, real-engine tests, benchmark, probes all ran; Linux wheels, not Windows wheels).

Not verifiable from metadata: whether the X270's CPU/OS build runs these onnxruntime wheels; whether a Microsoft Visual C++
Redistributable is required (commonly reported for DLL-load errors; the PyPI description does not state it).
Windows ARM is out of scope (the X270 is x64).

## 2. One-command validation (PowerShell)
Run from the repository root. Use a normal (non-admin) PowerShell.
```powershell
# Which Pythons are installed?
py -0p

# Python 3.11 (preferred) - full validation: install, lint, tests, real OCR, benchmark, probes
.\scripts\validate_windows.ps1 -PythonVersion 3.11 -Label "X270 on AC power"

# Python 3.12
.\scripts\validate_windows.ps1 -PythonVersion 3.12 -Label "X270 on AC power"
```
If script execution is blocked: `powershell -ExecutionPolicy Bypass -File .\scripts\validate_windows.ps1 -PythonVersion 3.11`
(affects only that process; review the script first). Logs and JSON land in `results\` (git-ignored). Nothing is deleted.

## 3. Manual steps (what the script automates)
```powershell
py -3.11 -m venv .venv311
.\.venv311\Scripts\python.exe -m pip install --upgrade pip
.\.venv311\Scripts\python.exe -m pip install -r requirements-dev.txt -c constraints\windows-cp311.txt
.\.venv311\Scripts\python.exe -m pip check
.\.venv311\Scripts\python.exe -c "import onnxruntime as o; print(o.__version__, o.get_available_providers())"
.\.venv311\Scripts\python.exe -m ruff check .
.\.venv311\Scripts\python.exe -m pytest -q                       # mock engine, 44+ tests
.\.venv311\Scripts\python.exe -m pytest -q -m requires_model -s   # REAL engine, network blocked
.\.venv311\Scripts\python.exe -m scripts.benchmark_ocr --runs 5 --warmup 2 --label "X270 AC"
.\.venv311\Scripts\python.exe -m scripts.probe_server
```
(For 3.12 replace `311` with `312`.) Run the server for the UI:
```powershell
Copy-Item .env.example .env        # once
.\.venv311\Scripts\python.exe -m apps.api      # http://127.0.0.1:8000  (Ctrl+C to stop)
```
Using `.\.venv\Scripts\Activate.ps1` also works; the commands above avoid activation so the execution policy does not matter.

## 4. Offline operation
After `pip install`, nothing needs the internet: the OCR model files ship inside the `rapidocr-onnxruntime` wheel; the
`requires_model` tests block all non-loopback sockets and pass on Linux. Native libraries can open sockets that Python
cannot see, so confirm on the X270 (item M-9 below).

## 5. Troubleshooting
- `py` not found / wrong version: install 64-bit Python 3.11 or 3.12 from python.org; `py -0p` lists versions.
- `onnxruntime` import fails with a DLL error: install the Microsoft Visual C++ Redistributable (x64) and retry (unverified cause).
- pip tries to build a wheel: you are on an unsupported Python (e.g. 3.13/3.14, 32-bit). Use 3.11/3.12 64-bit.
- Out of memory: close the browser/IDE; keep `VISTA_WORKER_CONCURRENCY=1`.
- Port busy: set `VISTA_PORT` in `.env`.

## 6. Manual X270 checklist (record the result next to each item)
- [ ] M-1 Hardware recorded: CPU model, RAM, Windows build, power mode (AC/battery), `py -0p` output.
- [ ] M-2 `validate_windows.ps1` finishes for Python 3.11; `summary.txt` has no FAIL on required steps.
- [ ] M-3 Same for Python 3.12 (or note which version you will standardize on).
- [ ] M-4 `pytest -m requires_model` passes (real OCR) - attach the log.
- [ ] M-5 Benchmark JSON saved; compare with the Linux numbers in RESOURCE_BUDGET.md (do not mix them).
- [ ] M-6 Task Manager during the benchmark: peak RAM of `python.exe` and total system RAM used with browser+IDE open.
- [ ] M-7 UI: open http://127.0.0.1:8000, upload `tests\fixtures\printed_en.png`, boxes align with the text, Copy works, Clear empties preview/text/boxes.
- [ ] M-8 UI error paths: upload a `.txt` renamed `.png`; upload a file larger than `VISTA_MAX_UPLOAD_BYTES`; both show a clear error.
- [ ] M-9 Offline check: disconnect Wi-Fi/Ethernet (or block `python.exe` outbound in Windows Firewall) and repeat M-4/M-7; also look at
      `python.exe` connections with Resource Monitor/`netstat -ano` during OCR. Note any outbound attempt. Also note files that
      appear in `%TEMP%` (onnxruntime writes `.ses`; see audit finding F-6).
- [ ] M-10 Stop test: start `python -m apps.api`, press Ctrl+C during an OCR request; the process exits (record seconds) and no `python.exe` remains.
- [ ] M-11 `probe_server` result for the shutdown probe on Windows (CTRL_BREAK path is unverified).
- [ ] M-12 Real photo (your own, non-sensitive): record whether text/boxes are acceptable; no claim of accuracy beyond that sample.
- [ ] M-13 Firewall: first run may show a Windows Firewall prompt; with the default `127.0.0.1` bind choose Cancel/Deny - it is not needed.
