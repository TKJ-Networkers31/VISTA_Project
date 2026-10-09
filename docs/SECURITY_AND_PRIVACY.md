# Security and Privacy

Status: design requirements for future code. Nothing here is implemented yet.

## File upload validation
- Allow-list of types (default JPEG, PNG, WebP). Verify by decoding, not by extension or client MIME alone.
- Reject truncated/corrupt images; strip or ignore metadata (EXIF) and do not log it.

## Limits
Configurable (see `.env.example`): max bytes, max side, **max total pixels** (decompression-bomb defense; set the decoder's pixel cap and check dimensions before full decode). Do not promise unlimited size.

## Temporary files
Prefer in-memory handling. If files are needed, use a private temp dir, random names, and delete in `finally`. Never use client-supplied filenames for paths.

## Resource exhaustion
Bound concurrency, queue depth, request time, and model memory. Reject early. Live mode drops stale frames instead of queueing.

## Local network exposure
Bind to `127.0.0.1` by default. LAN access (needed for phone testing) is an explicit opt-in; document that it exposes the service to the network and add authentication or a trusted-network warning before enabling.

## Raw image retention
Default `false`. Retention requires explicit config and is documented per feature.

## Secrets
Only in `.env` (git-ignored). `.env.example` has no real values. Never log secrets.

## OCR prompt injection
Text recovered by OCR is **untrusted data**. When passed to an LLM (Phase 7) it is delimited as data, never merged into instructions; the LLM has no tool access that could act on it.

## Logging privacy
Log request IDs, status, durations, and error codes. Do not log image bytes, OCR text, or detected content by default.

## Archive extraction (future, if ever)
Not planned. If considered: guard against zip-slip path traversal, zip bombs (ratio and total-size caps), symlinks, and nested archives; extract to an isolated temp dir.

## Third-party providers
Cloud STT/LLM/OCR would send user data off-device. Requires explicit opt-in and an ADR.
