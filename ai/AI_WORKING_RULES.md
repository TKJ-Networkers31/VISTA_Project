# AI Working Rules

Mandatory for every AI coding agent working on VISTA.

1. Read the relevant docs in `docs/` before coding.
2. Audit the repository and `git diff` first.
3. Never assume a file exists; check.
4. Make no changes outside the task scope.
5. Do not change architecture without owner approval (see `docs/ADR/`).
6. Never delete or overwrite the user's work.
7. Never run destructive Git commands (`reset`, `clean`, `checkout --`, force push) and never commit or push without explicit instruction.
8. Never fabricate test results, OCR output, detections, coordinates, or benchmarks.
9. Make small, tested changes.
10. Update documentation when behavior changes.
11. Do not add heavy dependencies without a recorded decision; verify versions before pinning.
12. Report: files changed, tests run, actual results, known limitations.
13. Stop and ask a human on architecture conflicts or undecided important decisions.
14. Do not claim a feature exists unless it is implemented and tested.
15. Keep 2D bbox, camera-space, and world-space strictly separate.
