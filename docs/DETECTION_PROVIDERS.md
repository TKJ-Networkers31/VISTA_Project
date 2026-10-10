# Detection providers
Select with `VISTA_DETECTION_BACKEND` (restart required): `yolox-onnx`/`yolox_nano` (default baseline),
`yolo26n_onnx`, `open_vocabulary` (experimental, unsupported). One `DetectionProvider` is registered with the shared
`ModelManager` as "detection"; OCR/detection residency rules are unchanged.

## YOLO26n
Export in a SEPARATE environment (Python 3.11/3.12; ultralytics/torch wheels for 3.14 are unverified):
  py -3.11 -m venv .venv-export; .\.venv-export\Scripts\python -m pip install ultralytics onnx
  .\.venv-export\Scripts\python scripts\export_yolo26n.py --imgsz 640
Then set the env vars printed by the script in `.env`. Weights: Ultralytics AGPL-3.0 or Enterprise (owner decision).
The provider accepts only `[1,4+C,A]` or `[1,N,6]` outputs and fails closed otherwise. The preprocessing contract
(RGB, /255, centered letterbox pad 114) comes from Ultralytics behavior and must be confirmed on the exported file.

## Open-vocabulary (status: unsupported)
Not verified: weights/license, ONNX export of Grounding DINO or alternatives, tokenizer/text encoder, operators, RAM.
Next experiments (in a separate env, one candidate at a time): check the export for unsupported ops with
`onnxruntime.InferenceSession`, measure peak RSS with the benchmark sampler, then write a provider that implements
`detect(..., prompt=...)` and a real text+image test. Until then `status` stays `unavailable`.

## Request/response
`POST /api/v1/detection?confidence=0.4&prompt=red%20cup` (`prompt` optional, 1-200 chars, only for backends with
`supports_prompt: true`, otherwise 400 `PROMPT_NOT_SUPPORTED`). Schema `0.3-detection` unchanged; `parameters.prompt`
is new and null by default. `GET /api/v1/detection/capabilities` adds `backend`, `family`, `supported`, `experimental`,
`supports_prompt`, `classes`, `runtime`, `limitations`, `license`.

## Rollback
Remove `VISTA_DETECTION_BACKEND` (or set `yolox-onnx`), `VISTA_DETECTION_MODEL_PATH=models/yolox_nano.onnx`,
`VISTA_DETECTION_MODEL_ID=yolox-nano`, `VISTA_DETECTION_INPUT_SIZE=416`; restart. Models are never deleted.

## Benchmark
python -m scripts.compare_detection_backends --spec ...   (latency/RAM, identical inputs)
python -m scripts.eval_detection --images D:\eval\images --annotations D:\eval\annotations.json   (needs ground truth)
Synthetic benchmark inputs measure latency only, never accuracy.