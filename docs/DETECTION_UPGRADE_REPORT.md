# Detection upgrade report (YOLO26 providers)

Status: provider abstraction implemented; YOLO26n/s load and run on the dev laptop; accuracy NOT measured.

## Environment
Intel Core i7-7500U, Windows, CPU only, onnxruntime 1.31.0, export env Python 3.14.0 / ultralytics 8.4.175 / torch 2.14.1+cpu.
Models exported with scripts/export_yolo26n.py (FP32, imgsz 640). Weights license: Ultralytics AGPL-3.0 or Enterprise (owner decision open).

## Measured (provider level, synthetic images, n=80 per model, one process for both models)
| Model | median | p95 | RSS peak | first inference |
|---|---|---|---|---|
| yolo26n.onnx | 98.0 ms | 127.2 ms | 210.8 MB | 95.7 ms |
| yolo26s.onnx | 256.1 ms | 316.9 ms | 320.1 MB* | 239.4 ms |
*Measured after yolo26n in the same process; likely overstated. Re-run with the isolated compare script.
Synthetic images contain no objects (0 detections): latency only, nothing about accuracy. Power mode and background load were not recorded.
The first result entry was labeled "yolo26s" by a script defect (model id taken from .env); the file loaded was yolo26n (sha256 52194e8f...).

## Not yet measured
Accuracy (precision/recall, false positives) on labeled photos; YOLOX-Nano on this laptop; OCR + detection coexistence;
end-to-end realtime FPS in the browser; output layout actually used (capabilities `layout` after the first request).

## Known limits
Closed 80-class COCO vocabulary: objects such as pens and calendars are mapped to the nearest COCO class (e.g. laptop, book).
open_vocabulary is unsupported (no verified model). Model is selected by .env + restart only.

## Rollback
VISTA_DETECTION_BACKEND=yolox-onnx, MODEL_PATH=models/yolox_nano.onnx, MODEL_ID=yolox-nano, INPUT_SIZE=416, SHA256 empty.