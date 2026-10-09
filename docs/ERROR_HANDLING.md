# Error Handling

Principle: honest degradation. Return structured errors/statuses; never fabricate results.

## Categories (match [DATA_CONTRACTS.md](DATA_CONTRACTS.md))
`invalid_input`, `unavailable`, `timeout`, `cancelled`, `quota_exceeded`, `auth_failed`, `network`, `provider_internal`, `resource_limit`, `not_implemented`.

## HTTP mapping (proposed)
| Category | HTTP |
|---|---|
| invalid_input | 400 / 413 / 415 |
| resource_limit | 429 or 503 |
| unavailable, not_implemented | 200 with capability status when other capabilities succeeded, else 501/503 |
| timeout | 504 (or per-capability `failed` in a partial result) |
| auth_failed (external) | capability `failed`; 502 if nothing else succeeded |
| provider_internal, network, quota_exceeded | per-capability `failed` / 502 |
| cancelled | 499-style or 200 with task state `cancelled` |

## Boundaries
1. API validates the request → `invalid_input`.
2. Orchestration enforces queue, timeout, cancellation → `resource_limit`, `timeout`, `cancelled`.
3. Provider adapters translate engine/library/network exceptions into typed provider errors; raw exception text and secrets never reach clients.

## Partial results
Envelope `status` = `partial` when some capabilities succeed and others fail; `errors[]` lists each failure with `capability` and `provider_id`.

## Retry
Only `retryable` errors, bounded count with backoff, within the cost budget. No infinite retries.

## Client-facing messages
Short, actionable, no stack traces, no file paths, no secret values.
