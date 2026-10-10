# Resource Budget

Resource limits are first-class requirements. Target: Lenovo ThinkPad X270, Core i7 7th gen, 8 GB RAM, NVMe SSD, Windows, CPU-only **[Assumption: verify by inspecting the actual machine]**. All numeric values below are **provisional configuration defaults**, not measurements, except the section "Measured results" at the end, which is labeled by machine. No benchmark has been run on the X270 yet.

## Memory (8 GB total)
Windows, browser, and IDE consume a large share. Budget policy: keep the VISTA process modest; at most `VISTA_MAX_RESIDENT_MODELS` (default 1) heavy model loaded at once, enforced by `ModelManager` for OCR and detection (idle models are unloaded to make room; memory reclamation by the OS is not guaranteed); lazy load on first use; unload after `VISTA_MODEL_IDLE_UNLOAD_SECONDS` is **not implemented**. Measured peak RSS per provider is recorded here after Phase 2/3.

## Queues and concurrency
Bounded queue (`VISTA_QUEUE_MAX_SIZE`) and worker count (`VISTA_WORKER_CONCURRENCY`, default 1). Full queue → immediate `resource_limit` rejection, never unbounded buffering.

## Image limits
`VISTA_MAX_UPLOAD_BYTES`, `VISTA_MAX_IMAGE_SIDE`, `VISTA_MAX_IMAGE_PIXELS` — configurable, checked before full decode. Large images are downscaled for inference but results map back to original pixels.

## Timeouts and cancellation
Per-task timeout (`VISTA_TASK_TIMEOUT_SECONDS`); cooperative cancellation at checkpoints; client disconnect cancels queued work.

## Frame sampling (Phase 5)
Sample at a configurable rate below measured throughput; bounded frame queue; **drop oldest** when full; count and expose dropped frames in metrics. Never accumulate frames.

## API cost controls
External calls disabled by default. Per-request retry cap (`VISTA_EXTERNAL_RETRY_MAX`), per-call timeout, and (Phase 4) configurable daily call/cost ceiling. Never retry indefinitely.

## Benchmarks to run (when code exists)
For each provider on the reference laptop, record: cold-start load time, warm latency per image size, peak RAM, CPU utilization, throughput over a fixed fixture set. Store results with hardware and software versions. Until recorded, state "not measured".

## Stop/disable policy
If available memory falls below a configured floor, or a task exceeds its timeout repeatedly: reject new heavy tasks with `resource_limit`, unload idle models, and report the condition in `/health`. Resume when conditions recover. Thresholds are to be set from measurements (**[Open]**).

## Measured results

How to reproduce: `python -m scripts.benchmark_ocr --runs 5 --warmup 2` (6 synthetic fixtures in `tests/fixtures`, so 30 timed
samples after warm-up; with n=30 the p95 is close to the maximum). Latency is end-to-end service time (validate, decode, downscale, OCR, normalize). RSS is the benchmark process.
CPU utilization was not measured. "Similarity" (text overlap with known fixture text) was 1.0 on every fixture, which only says that clean synthetic text was read; it is not an accuracy figure.

### Linux sandbox — NOT the X270 (1 logical CPU, CPU model not recorded, Linux x86_64, glibc 2.39)
| Run | Python | onnxruntime | numpy | model load | first OCR | median (warm) | p95 (warm) | RSS before load | RSS after load | RSS peak during OCR |
|---|---|---|---|---|---|---|---|---|---|---|
| Windows-resolved pins, cp311 | 3.11.17 | 1.31.0 | 2.4.6 | 0.34 s | 1682.5 ms | 917.6 ms | 1138.3 ms | 70.7 MB | 150.0 MB | 633.8 MB |
| Windows-resolved pins, cp312 | 3.12.3 | 1.31.0 | 2.5.3 | 0.32 s | 1795.4 ms | 1018.0 ms | 1204.8 ms | 68.7 MB | 148.1 MB | 579.4 MB |
| Earlier env (3 runs/image only) | 3.12.3 | 1.30.0 | 2.5.3 | 0.56 s | 2975.1 ms | 967.8 ms | 1613.7 ms | 65.1 MB | 140.3 MB | 592.8 MB |

Server process peak RSS while 10 concurrent large-image requests were sent (capacity 3, probe `backpressure`): 507.9 MB (3.11), 514.4 MB (3.12).
Model load time depends on the OS file cache: an earlier ad-hoc first-ever load in the same sandbox took about 10.5 s (single measurement, not from the script).
Expect the first start on the X270 to be slower than the table.

### Detection (YOLOX-Nano, ONNX Runtime CPU) — Linux sandbox, NOT the X270
How to reproduce: `python -m scripts.benchmark_detection --runs 5 --warmup 2` (4 deterministic synthetic images, so 20 timed
samples; p95 ~ max). Provider-level latency (letterbox + inference + decode/NMS), no HTTP or image decoding.
Environment: 2 logical CPUs, 8 GB, CPU model not recorded, Linux x86_64, glibc 2.39, **Python 3.13.16**, onnxruntime 1.29.0,
numpy 2.5.3 (not the pinned 1.31.0 of the constraints files), `VISTA_DETECTION_THREADS=0`. Model SHA-256 `c789161e…a0b7d`.

| Image | median | p95 | preprocess / inference / postprocess (median) |
|---|---|---|---|
| 640x480 | 19.3 ms | 24.7 ms | 3.9 / 14.4 / 1.4 ms |
| 1280x720 | 24.5 ms | 28.0 ms | 6.4 / 16.7 / 1.4 ms |
| 1920x1080 | 27.1 ms | 35.5 ms | 9.8 / 15.6 / 1.4 ms |
| 3000x2000 | 38.2 ms | 62.6 ms | 23.5 / 13.6 / 1.4 ms |

Overall median 24.8 ms, p95 55.0 ms (n=20). Model load 0.04 s (file cache warm), first inference 21.0 ms.
Process RSS (whole process): 127.3 MB before load, 134.4 MB after load, 140.0 MB after the first inference, 145.0 MB peak.
These show that the model itself is small; they are **not** X270 numbers, and the OCR and detection models together were
**not** measured. The first-ever load from a cold disk cache will be slower. Synthetic images contain no objects, so
detection counts in that run were 0 and say nothing about accuracy. One end-to-end API request on the 768x576 demo photo
reported `processing_time_ms` 154.5 (first request, includes model load and decoding).

### ThinkPad X270 (Windows, Python 3.11/3.12) — **not measured**
Latency, peak RAM, CPU utilization, and total-system memory pressure with browser/IDE open: pending `scripts\validate_windows.ps1` on the X270 (OCR) and `python -m scripts.benchmark_detection` (detection, see [DETECTION.md](DETECTION.md#9-benchmark)). OCR + detection coexistence under `VISTA_MAX_RESIDENT_MODELS=1` and `=2` also still needs measuring.
Do not derive X270 budgets from the Linux table.
