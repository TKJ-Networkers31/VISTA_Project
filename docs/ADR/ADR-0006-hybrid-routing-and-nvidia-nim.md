# ADR-0006: Hybrid routing policy and NVIDIA NIM as the external image-understanding provider

- **Status:** Proposed (awaiting owner decision). Implemented in the working tree; nothing is committed.
- **Date:** 2026-10-10 (Phase 4)

## Context
Phase 4 adds an external provider behind explicit policy (ADR-0002). Local OCR and detection must stay the default
path. The only capability with no local provider is free-text image understanding (question about an image).

## Decision
1. **Policy as pure code:** `core/routing/policy.py` (`decide`, `may_fallback`) holds every routing rule; handlers and
   adapters contain no mode logic. `local_only` never goes external; `hybrid` goes external only for capabilities listed
   as external and with consent; `external_fallback` is local-first and external only after an eligible failure with consent.
2. **Consent is per request** (`consent_external=true` form field, default rejected) AND requires the master switch
   `VISTA_EXTERNAL_ENABLED=true` and a configured key. All three must hold.
3. **One new capability, one new contract:** `POST /api/v1/understanding`, schema `0.4-understanding`. OCR (`0.2-ocr-mvp`) and
   detection (`0.3-detection`) are untouched. The response carries `route` including `external_transmission`.
4. **Adapter:** `core/providers/nim.py`, hosted `https://integrate.api.nvidia.com/v1/chat/completions`, stdlib `urllib`
   (no new dependency), https + host allow-list, no redirects, bounded retries (429/503 only, 0..3), per-attempt timeout,
   daily in-memory call ceiling (`CallBudget`), key only in the Authorization header.
5. **The image is re-encoded** (JPEG, longest side <= `VISTA_UNDERSTANDING_MAX_SIDE`, <= `VISTA_NIM_MAX_IMAGE_BYTES`),
   so metadata is dropped and the payload is bounded.
6. **No silent substitution:** understanding is never answered by OCR/detection output, and a vision-language answer is
   never presented as boxes. `provides_bounding_boxes` is `false`.
7. **Not adopted:** Colab as a runtime provider, self-hosted NIM, YOLO-World as a Phase 4 dependency.

## Alternatives considered
- Global consent flag only: simpler but allows sending without a per-action decision.
- `requests`/`httpx` for the call: nicer API, but a new runtime dependency for one POST.
- Streaming responses: lower perceived latency; rejected because the contract needs one complete answer.
- Treat the hosted free endpoint as production: rejected; availability, quota and terms are unverified.

## Consequences
+ Nothing leaves the machine by default; every send is provable from the response and from tests.
+ Local features keep working with the provider disabled, missing or down.
- Image understanding depends on a third party; the daily ceiling resets on restart; the inline size limit and the
  effect of `enable_thinking` are unverified until a live run.

## Re-evaluation conditions
Live test results; NVIDIA terms/quotas for the free endpoint; a second external provider; a need for boxes from a
grounding model; X270 measurements of routing overhead; project license decision.
