# Resource Budget

Resource limits are first-class requirements. Target: Lenovo ThinkPad X270, Core i7 7th gen, 8 GB RAM, NVMe SSD, Windows, CPU-only **[Assumption: verify by inspecting the actual machine]**. All numeric values below are **provisional configuration defaults**, not measurements. No benchmark figures exist yet.

## Memory (8 GB total)
Windows, browser, and IDE consume a large share. Budget policy: keep the VISTA process modest; at most `VISTA_MAX_RESIDENT_MODELS` (default 1) heavy model loaded at once; lazy load on first use; unload after `VISTA_MODEL_IDLE_UNLOAD_SECONDS`. Measured peak RSS per provider is recorded here after Phase 2/3.

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
