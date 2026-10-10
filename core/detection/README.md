# core/detection

**Status:** implemented (Phase 3), verified in a Linux sandbox; not yet validated on the X270.

YOLOX/ONNX Runtime provider (`yolox_onnx.py`), pure-numpy letterbox/decode/NMS (`geometry.py`), conversion of raw
backend output into validated contract objects (`normalize.py`), COCO labels, backend registry. Imports contracts and
provider interfaces only; the API never sees backend objects. Details: [docs/DETECTION.md](../../docs/DETECTION.md).
