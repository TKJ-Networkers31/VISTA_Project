# VISTA 3.2 upgrade report

**Status: PARTIALLY DONE. Phases 2 and 6 are BLOCKED in the environment this was produced in.**

## What this session could and could not do
The repository was NOT available on disk. I only had the file contents pasted into the conversation. There was no network,
no model weights, and no fastapi, pytest or ruff. So nothing below was run against your checkout, your working tree or git
state (Phase 0 "inspect branch/working tree" was impossible), and the existing test suite was not run.

## Executed here (sandbox: Linux, Python 3.12.3, numpy 2.4.4, onnxruntime 1.24.4)
| Check | Result |
|---|---|
| `py_compile` of the 3 new files | OK |
| `tests/test_ort_options.py` via a minimal pytest shim (real pytest absent) | 6 checks passed |
| `scripts/benchmark_ort_threads.py` end to end | NOT run: no model file and no `onnx` package to build one |
| ruff, full pytest, node tests, real-model tests | NOT run |

## Delivered (new files, nothing existing overwritten)
- `core/detection/ort_options.py`: one place for SessionOptions (intra threads, inter-op threads, sequential/parallel). Defaults equal the old behaviour.
- `scripts/benchmark_ort_threads.py`: one child process per config (1/2/4 intra threads, sequential vs parallel), interleaved repeats, median-of-medians, spread, worst p95, peak RSS. It states when differences are inside the noise.
- `tests/test_ort_options.py`.

## Edits for you to apply (exact, small)
1. **B905** (`zip` without `strict=`), 3 sites found by reading the pasted code (ruff itself was not run):
   - `core/detection/yolox_onnx.py`: `zip(boxes, scores, class_ids)` -> `zip(boxes, scores, class_ids, strict=True)`
   - `core/detection/yolo26_onnx.py`: `zip(boxes, scores, ids)` -> `zip(boxes, scores, ids, strict=True)`
   - `scripts/audit_detection_pipeline.py`: `zip(boxes, scores, ids)` -> `zip(boxes, scores, ids, strict=True)`
   strict=True is safe: the three arrays come from the same index set and have equal length by construction.
2. **Use the helper** in both providers' `load()`: replace the block
   `options = ort.SessionOptions(); options.log_severity_level = 3; if self._settings.detection_threads > 0: ...`
   with `options = build_session_options(ort, self._settings.detection_threads)` and
   `from .ort_options import build_session_options`. Behaviour is unchanged until you add settings.
3. **Optional settings** (only after measuring): add `detection_inter_op_threads: int = 0` and
   `detection_exec_mode: str = "sequential"` to `Settings`, parse them in `from_env` with `_int` / `_choice(EXEC_MODES)`,
   pass them as the 2nd and 3rd helper arguments, and document them in `.env.example`, CONFIGURATION.md, DETECTION.md.

## Run on the X270 (Phase 1 evidence)
```powershell
python -m pip install psutil
python -m scripts.benchmark_ort_threads --model models\yolox_nano.onnx --size 416 --repeats 3 --label "X270 AC, browser closed"
python -m scripts.benchmark_ort_threads --model models\yolo26n.onnx --size 640 --repeats 3 --label "X270 AC, browser closed"
```
Pick the thread setting from the summary only if it beats the others by more than the printed spread. No X270 number exists yet.

## Source audit of the pasted code (read, not executed; observations, not measurements)
- Already present: bounded admission per service (`worker_concurrency + queue_max_size`), timeouts, cooperative cancel,
  shutdown, `ModelManager` (one heavy model by default), model load inside worker threads (not on the event loop),
  client-side single-flight realtime loop with stale-result dropping, upload limits checked before full decode.
- Gap 1: stale frames are discarded only client-side. The server has no "newest frame wins" policy; a slow server with
  several clients would queue old frames up to capacity (then 429).
- Gap 2: OCR and detection have separate pools and queues. With `VISTA_MAX_RESIDENT_MODELS=1` they serialize through
  `ModelManager`, but with 2 they may run concurrently on 2 cores. Not measured; keep 1 until it is.
- Gap 3: a request inside `session.run` cannot be cancelled (documented). Timeouts free the client, not the CPU.
- Gap 4: no server-side CPU/RSS metric endpoint; diagnostics exist only in benchmark scripts.
- I did not change any of these: they need measurements and a decision, and changing them blind would risk the working realtime path.

## Phase 2 (detection research): BLOCKED, documented, nothing claimed
No network, no weights, no ONNX tooling here, so YOLO-World, Grounding DINO and OWL-ViT were not exported, loaded or run.
Their licenses, tokenizers, operators, RAM and latency are all UNVERIFIED. `open_vocabulary` stays `unavailable`.
Baseline YOLOX-Nano / YOLO26 are untouched; rollback is the existing section in `docs/DETECTION_PROVIDERS.md`.
Suggested bounded attempt on a machine with network: one candidate (YOLO-World), 1 session, export in a separate venv,
check operators with `onnxruntime.InferenceSession`, run 3 real photos with 3 prompts, record RSS. Stop if it does not load.

## Not done
Phase 3 (pipeline consolidation), Phase 4 (OCR+detection combined workflow), Phase 5 (product milestone), Phase 6
(stress, memory-growth and labeled-accuracy tests). Existing `scripts/eval_detection.py` covers the accuracy harness once you have labeled images.

## Next milestone
1. Apply edits 1-2, run ruff and the full suite on the X270 and paste the output.
2. Run the thread benchmark and decide the setting.
3. Then the best non-detection milestone is likely a combined OCR + detection result export (JSON/copy) on the existing pages,
   but that should be scoped against the real checkout.
