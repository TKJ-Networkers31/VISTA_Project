# Phase 4 measurements (image understanding via NVIDIA NIM)

Only values observed on the owner's machine (ThinkPad X270, Windows, hosted NVIDIA endpoint, model
`nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`) are listed. Everything else says "not measured". Do not extrapolate.
Each row is ONE run: no median, no p95, no distribution exists yet.

## A. Web page, server log (`vista.api ... understanding ...`, 2026-10-10)
| Request | Mode | Result | `ms` | Bytes uploaded | JPEG sent |
|---|---|---|---|---|---|
| 1 | hybrid | `NIM_TIMEOUT` (limit then 30 s) | 32637.7 | 157,558 | 1024x572, q85, 137,275 B |
| 2 | hybrid | `NIM_TIMEOUT` (limit then 30 s) | 30445.9 | 157,558 | 1024x572, q85, 137,275 B |
| 3 | external_fallback | answered (free text, network-topology image) | NOT RECORDED | not recorded | 1024x572, q85, 137,275 B |

## B. `python -m scripts.diagnose_nim --timeout 180` (provider call only, no retries, one run each)
Server settings at the time: external_timeout=150 s, retry_max=1, task_timeout=320 s.

Synthetic images (flat shapes, tiny files, NOT comparable to photos):
| Case | Size sent | Result | Seconds |
|---|---|---|---|
| text only | n/a | HTTP 503 `ResourceExhausted: Worker local total request limit reached (16/16)` | 3.5 |
| 64 px | 1,239 B | `NIM_SERVER_ERROR` (HTTP status not shown by this script version) | 2.8 |
| 256 px | 3,251 B | answered | 2.0 |
| 512 px | 7,111 B | `NIM_SERVER_ERROR` (same note) | 1.6 |
| 768 px | 12,087 B | answered | 2.2 |
| 1024 px | 17,967 B | answered | 3.1 |

Owner's own image (source 1024x1877 px PNG, re-encoded like the server does):
| Longest side | JPEG size | Result | Seconds |
|---|---|---|---|
| <= 1024 px | 86,815 B | answered | 2.1 |
| <= 768 px | 57,099 B | answered | 4.4 |
| <= 512 px | 29,617 B | answered | 1.8 |

## C. Web page, server log after the settings fix (2026-10-11; `vista.config` line: external_timeout=150 s, retry_max=1, task_timeout=320 s, understanding_max_side=768)
| Request | Mode | Result | `ms` (server pipeline) | Bytes uploaded |
|---|---|---|---|---|
| 4 | hybrid | succeeded | 4619.8 | 83,574 |
| 5 | hybrid | succeeded | 27203.3 | 100,387 |
`ms` covers decode, JPEG re-encode and the provider call (including retry waits); it excludes time spent waiting in the
queue. Locally it is small next to the provider call, but the local share was NOT measured separately.
Request 5 took 27 s: just under the old 30 s limit, so with the old setting it would likely have timed out. Two
successful requests on one day are not a distribution; latency of this shared endpoint varies by at least 6x here.

## What this does and does not show
- The provider itself reported that its worker was saturated (HTTP 503, 16/16 requests). The failures with synthetic
  images in section B are fast (1.6 to 3.5 s) and intermittent, so they are consistent with provider-side capacity
  limits on a shared endpoint. The 64 px and 512 px failures were not shown with their HTTP status: they are
  assumed, not proven, to be the same 503.
- The two 30 s timeouts in section A were slow responses, not fast errors: a different symptom. Their cause is NOT
  established (provider load is one possibility; image size alone does not explain it, because 86,815 B and
  137,275 B images were both within range of what answered here).
- The provider accepted an inline image of 137,275 B (about 183,000 base64 characters). The 180,000 B default of
  `VISTA_NIM_MAX_IMAGE_BYTES` is a conservative cap, not a provider limit.
- The response shape `choices[0].message.content` parsed successfully on every answered call.
- Answer QUALITY is not established. For the owner's image the three sizes returned three different lists
  (e.g. "Rubik's Cube, buku, pensil..." at 768 px versus "Alat tulis, Pencolok, Pena" at 512 px). Inconsistent
  answers to the same image and question mean the output must be checked against the image before use.
- Not measured: server-side `ms` for answered requests, local re-encode time, routing overhead, RSS of the VISTA process
  during an external request, behaviour of `enable_thinking=false`, quota, repeated-request behaviour.

## Paste into docs/RESOURCE_BUDGET.md (section "Image understanding, external", labeled X270 + hosted NVIDIA)
Provider-call time for a re-encoded JPEG of 29.6 KB to 86.8 KB (one real image, one run each): 1.8 s to 4.4 s.
Two earlier web requests with a 137 KB JPEG timed out at the then 30 s limit; two later web requests succeeded in 4.6 s and 27.2 s (server `ms`). The hosted endpoint answered HTTP 503
"Worker local total request limit reached (16/16)" at least once. No distribution, no RAM figure, no routing
overhead was measured. These numbers describe a shared free endpoint on one day and must not be used as a budget.
