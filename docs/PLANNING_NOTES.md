# Planning Notes

## Hardware constraints
X270, i7 7th gen (dual-core/4-thread class **[Assumption: verify]**), 8 GB RAM, no useful GPU assumed. Policies in [RESOURCE_BUDGET.md](RESOURCE_BUDGET.md).

## Technical risks
- OCR/detection frameworks may be heavy or hard to install on Windows.
- CPU latency may make live mode coarse; no real-time claim until measured.
- Browser camera access on a phone generally needs a secure context (HTTPS) except localhost **[Assumption: verify]**.
- Spatial features need pose/depth that a browser alone may not provide.
- External providers add cost, privacy, and availability risk.

## Assumptions to test
1. A local OCR engine fits the RAM budget and runs acceptably on the X270.
2. A lightweight detector reaches usable CPU speed.
3. Python 3.11 is installed or installable and compatible with chosen libraries.
4. Android browser can reach the local server safely.

## Open questions (owner)
1. License ([../LICENSE_DECISION.md](../LICENSE_DECISION.md)).
2. OCR languages (e.g. Indonesian, English).
3. Which external providers, if any, and monthly cost ceiling.
4. Target XR/Android device.
5. Security contact for SECURITY.md and CODE_OF_CONDUCT.md.
6. Authentication mechanism before any LAN exposure.
7. Resource-pressure thresholds (after measurements).

## Low-cost strategy
Pretrained local models, CPU-only, external APIs off by default, no database until needed, measure before optimizing.
