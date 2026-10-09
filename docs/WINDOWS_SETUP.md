# Windows Setup (PowerShell)

Primary environment: Windows with PowerShell. Docker, WSL, a GPU, or paid APIs are **not** required. Steps marked **(future)** depend on code that does not exist yet.

## 1. Check tools
```powershell
python --version
py -0p              # lists installed Python versions
git --version
```
Preferred Python is 3.11 **[Proposal]**; confirm compatibility of your chosen libraries before settling.

## 2. Virtual environment
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```
If activation is blocked: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` (review the implication first).

## 3. Install dependencies
Foundation stage (dev tools only):
```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```
Runtime dependencies **(future)** are added in Phase 1 and documented here.

## 4. Environment file
```powershell
Copy-Item .env.example .env
```
Edit `.env` locally; it is git-ignored. Never commit it.

## 5. Tests
```powershell
python -m pytest
python -m ruff check .
```
At Phase 0 there are no tests, so pytest reports "no tests ran" (exit code 5). This is expected.

## 6. Start the server **(future, Phase 1)**
```powershell
# Command will be documented when apps/api exists.
```

## Troubleshooting
- **Wheel build failures:** use a Python version with prebuilt wheels for the library; avoid compiling on 8 GB RAM.
- **Long paths:** enable Windows long path support or keep the repo near the drive root.
- **Out of memory:** close the browser/IDE; keep `VISTA_MAX_RESIDENT_MODELS=1`.
- **Script execution policy:** see step 2.
- **Phone cannot reach server:** default bind is `127.0.0.1`; LAN exposure is a deliberate opt-in ([SECURITY_AND_PRIVACY.md](SECURITY_AND_PRIVACY.md)); allow only on a trusted network and check the Windows firewall prompt.
