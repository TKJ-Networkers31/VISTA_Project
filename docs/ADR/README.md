# Architecture Decision Records

An ADR records one significant decision so it is never changed silently.

## When to write one
Changing architecture, adding a major dependency, choosing a provider/model, changing a data contract, or altering a security default.

## Format
File name `ADR-NNNN-short-title.md` with: Status (Proposed/Accepted/Superseded), Context, Decision, Alternatives considered, Consequences, Re-evaluation conditions.

## Rules
- Accepted ADRs are not edited; supersede them with a new ADR.
- Only the project owner marks an ADR Accepted.
- Mirror each decision in [../../ai/DECISION_LOG.md](../../ai/DECISION_LOG.md).

## Index
- [ADR-0001: Modular monolith](ADR-0001-modular-monolith.md)
- [ADR-0002: Hybrid inference](ADR-0002-hybrid-inference.md)
- [ADR-0003: Spatial capability boundaries](ADR-0003-spatial-capability-boundaries.md)
