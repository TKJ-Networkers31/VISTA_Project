# OCR

**Engine:** `rapidocr-onnxruntime` (ONNX Runtime, CPU). Chosen because it installs from prebuilt wheels with models bundled (no separate download, no PaddlePaddle/PyTorch), returns polygons and confidence, and runs locally with no API key. Alternatives not evaluated here: Tesseract (needs a separate Windows install), EasyOCR/PaddleOCR (heavier).

**Flow:** validate (size, MIME, decode, side/pixel limits) → EXIF orient, flatten alpha → downscale to `VISTA_OCR_MAX_SIDE` for inference → lazy-load model once → raw engine output → normalize (map back to original pixels, group into lines, left-to-right/top-to-bottom order). Raw output is only returned with `include_raw=true`.

**Swap engine:** implement `core.providers.OCRProvider` (`info`, `is_available`, `is_loaded`, `load`, `recognize`), then register the name in `core/ocr/registry.py` and set `VISTA_OCR_ENGINE`.

**Limits / known behavior**
- Images are processed in memory; nothing is written by VISTA. (Starlette may spool uploads >1 MB to the OS temp dir during parsing and removes them; tested.)
- On timeout the worker thread cannot be killed; it stops at the next checkpoint, and its queue slot is freed only when it really finishes.
- Idle model unloading (`VISTA_MODEL_IDLE_UNLOAD_SECONDS`) is not implemented. Since Phase 3 the OCR model can be evicted to make room for the detection model when `VISTA_MAX_RESIDENT_MODELS=1` (never while a request uses it); it reloads on the next OCR request. See [DETECTION.md](DETECTION.md#7-ocr--detection-on-8-gb-what-is-and-is-not-guaranteed).
- Default languages are the engine's bundled Chinese/English models; Indonesian accuracy is unmeasured.
- Observed once on an earlier generated image: a space between two words was dropped ("OCRTEST"). The committed fixtures read back with 1.0 whitespace-insensitive similarity on Linux; accuracy on real photos is unmeasured.
- Engine/library artifacts: importing onnxruntime writes a small `.ses` file to the temp directory (see VALIDATION_AUDIT.md F-6).

**Measurements:** see `docs/RESOURCE_BUDGET.md` (Linux figures are labeled Linux; the X270 is not measured yet). The ad-hoc numbers quoted in the first MVP report were superseded by `scripts/benchmark_ocr.py`.
