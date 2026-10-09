# ADR-0002: Hybrid inference through provider adapters

- **Status:** Proposed (awaiting owner acceptance)

## Context
CPU-only 8 GB laptop; some capabilities (LLM, image understanding) are impractical locally; privacy and cost matter.

## Decision
All AI capabilities are accessed through a common provider interface with local and external adapters. Three explicit policies (`local_only` default, `hybrid`, `external_fallback`). External use requires explicit configuration and consent; failures degrade honestly. Details: [API_PROVIDER_POLICY.md](../API_PROVIDER_POLICY.md).

## Alternatives considered
- Local-only: private and free, but cannot deliver LLM-grade features on this hardware.
- External-only: simple and capable, but costs money, needs network, and sends user data out.
- Provider SDK calls directly in feature code: fast to write, but couples the codebase to vendors.

## Consequences
+ Swappable providers, testable with mocks, privacy by default.
− Adapter layer to maintain; policy/routing complexity; more configuration.

## Reconsider when
Hardware changes (e.g. GPU), a provider becomes dominant, or policy complexity outweighs benefit.
