# License Decision

**Status: pending — owner decision required.** No `LICENSE` file is included on purpose, because choosing a license is the project owner's decision. Without a license, default copyright applies (all rights reserved) and others may not legally reuse the code.

## Options to consider

| License | Summary | Consider when |
|---|---|---|
| MIT | Very permissive, minimal terms | You want maximum adoption |
| Apache-2.0 | Permissive plus explicit patent grant | You want patent clarity |
| GPL-3.0 | Strong copyleft; derivatives must stay open | You want improvements shared back |
| AGPL-3.0 | Copyleft covering network use | You expect hosted derivatives |
| Proprietary / none | Rights reserved | Project stays private or commercial |

## Check before deciding

- Licenses of candidate dependencies and model weights (some detection models carry copyleft terms, e.g. AGPL). Verify each; this document does not assert any.
- Whether contributions will be accepted (CLA/DCO).

## Next step

Owner records the choice in [ai/DECISION_LOG.md](ai/DECISION_LOG.md), then adds `LICENSE` and updates the README.
