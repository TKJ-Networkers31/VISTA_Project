# Security and Privacy

Status: design requirements for future code; nothing here is implemented yet.

## Secrets and `.env`
Secrets only in private `.env`/OS environment (git-ignored). `.env.example` contains no real values. Never log or echo secret values; config errors name the variable, not its value. Credential checks in the repo must not print values.

## Image and document validation
Allow-list of types; verify by decoding, not extension or client MIME alone. Reject corrupt/truncated files. Enforce bytes, side, and **total pixel** limits before full decode (decompression-bomb defense). Ignore/strip metadata and do not log it.

## Path traversal
Never use client-supplied names for paths. Generate random names inside a private temp directory; resolve and verify paths stay inside it.

## Archive extraction (future only)
Not planned. If added: guard against zip-slip, zip bombs (ratio and total-size caps), symlinks, nested archives, and extract into an isolated temp dir with entry-count limits.

## Resource exhaustion
Bounded queue and workers, timeouts, early rejection, per-IP rate limiting where exposed beyond localhost, bounded frame queues in live mode ([RESOURCE_BUDGET.md](RESOURCE_BUDGET.md)).

## API authentication and rate limiting
Localhost-only default needs no auth. Before any LAN or remote exposure: require an authentication token and rate limiting; document the exposure. **[Open]** exact mechanism chosen in Phase 5 (before live-camera LAN use) at the latest.

## Local network exposure
Bind `127.0.0.1` by default. LAN (e.g. for phone testing) is an explicit opt-in with a documented warning, firewall guidance, and auth.

## Logging and redaction
Log metadata only (see [OBSERVABILITY.md](OBSERVABILITY.md)); redact content and secrets by default.

## External data transmission
Off by default. Requires explicit configuration and policy ([API_PROVIDER_POLICY.md](API_PROVIDER_POLICY.md)); transmissions are visible as metadata. Images, audio, documents, and extracted text are never sent without that consent.

## OCR text and prompt injection
OCR output is untrusted data. When given to an LLM it is delimited as data, and the LLM has no tool permissions that could act on it.

## Temporary files, retention, deletion
Prefer in-memory processing; otherwise private temp dir deleted in `finally`. Raw images and audio are not retained by default (`VISTA_RETAIN_RAW_IMAGES=false`). If retention is ever enabled, document duration and provide deletion.

## Dependencies and vulnerability reporting
Add dependencies deliberately; check licenses; review updates regularly (e.g. dependency audit tooling once chosen). Vulnerabilities are reported per [../SECURITY.md](../SECURITY.md).
