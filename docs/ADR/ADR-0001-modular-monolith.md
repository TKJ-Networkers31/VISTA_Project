# ADR-0001: Modular monolith for early phases

- **Status:** Proposed (awaiting owner acceptance)
- **Date:** Phase 0

## Context
Single developer, limited hardware (ThinkPad X270, 8 GB RAM, CPU-only assumption), early uncertainty about engines, and a need for fast iteration.

## Decision
Build one deployable Python application with enforced internal module boundaries ([ARCHITECTURE.md](../ARCHITECTURE.md)).

## Alternatives considered
- **Microservices:** independent scaling, but multiplies processes and RAM use, adds network failure modes and operational overhead with no present need.
- **Single unstructured script:** fastest start, but hard to extend and test.

## Consequences
+ Simple setup, debugging, and testing; lower memory overhead.
− Components share a process; heavy models compete for RAM; scaling is vertical.
Boundaries make later extraction possible.

## Re-evaluation conditions
Revisit if a component needs independent scaling or different runtime/hardware (e.g. GPU worker, XR backend), if team size grows, or if measured contention between components blocks requirements.
