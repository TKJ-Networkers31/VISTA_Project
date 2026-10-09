# Planning Notes

## Hardware constraints
Core i7 7th gen, 8 GB RAM, likely no useful GPU [Assumption]. Models must be small; load lazily; one heavy model at a time if needed.

## Technical risks
- OCR/detection frameworks may be heavy or hard to install on Windows.
- CPU latency may make live mode (Phase 6) coarse.
- Phone camera access in browsers generally requires a secure context (HTTPS) except on localhost; LAN testing needs a plan. [Assumption: verify]
- Spatial features depend on device pose/depth that a plain browser may not provide.

## Assumptions to test
1. Chosen OCR runs within RAM budget on the reference laptop.
2. Chosen detector reaches usable speed on CPU.
3. Android browser can capture images/frames against the local server.

## Open questions (owner)
1. License choice ([../LICENSE_DECISION.md](../LICENSE_DECISION.md)).
2. Primary languages for OCR (e.g. Indonesian, English).
3. Target XR device (if any).
4. Local-only vs cloud LLM/STT in Phase 7.
5. Security contact for SECURITY.md and CODE_OF_CONDUCT.md.

## Low-cost strategy
Pretrained models, CPU-only, no cloud by default, no database until needed, measure before optimizing.
