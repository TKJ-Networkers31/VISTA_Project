"""YOLOX (ONNX Runtime, CPU) detection provider.

Runs a YOLOX ONNX model exported WITHOUT in-graph decoding (the official `yolox_nano.onnx` / `yolox_tiny.onnx`
release assets are of this kind: output `[1, anchors, 85]`). Decoding, NMS and box mapping live in
`core.detection.geometry`. The model file is never bundled or downloaded implicitly; see docs/DETECTION.md.
"""
from __future__ import annotations

import gc
import hashlib
import importlib.util
import threading
import time
from importlib import metadata
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from core.config import Settings
from core.contracts import DetectionModelInfo, EngineInfo
from core.providers import RawDetection, RawDetectionResult

from .coco_labels import COCO_CLASSES
from .geometry import expected_anchor_count, letterbox_image, postprocess_yolox

ROOT = Path(__file__).resolve().parents[2]


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_model_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else ROOT / path


class YoloxOnnxProvider:
    def __init__(self, settings: Settings, labels: Tuple[str, ...] = COCO_CLASSES) -> None:
        self._settings = settings
        self._labels = tuple(labels)
        self._path = resolve_model_path(settings.detection_model_path)
        self._size = settings.detection_input_size
        self._session: Any = None
        self._input_name: Optional[str] = None
        self._sha256: Optional[str] = None
        self._lock = threading.Lock()
        self.last_timings: Dict[str, float] = {}

    # -- identity --
    def info(self) -> EngineInfo:
        try:
            version = metadata.version("onnxruntime")
        except metadata.PackageNotFoundError:
            version = None
        return EngineInfo(id="onnxruntime", version=version, locality="local")

    def model_info(self) -> DetectionModelInfo:
        return DetectionModelInfo(id=self._settings.detection_model_id, family="yolox", input_size=self._size,
                                  num_classes=len(self._labels), sha256=self._sha256)

    # -- lifecycle --
    def is_available(self) -> Tuple[bool, Optional[str]]:
        for module in ("numpy", "onnxruntime"):
            if importlib.util.find_spec(module) is None:
                return False, f"Package '{module}' is not installed (pip install onnxruntime numpy)."
        if not self._path.is_file():
            return False, (f"Detection model file '{self._path.name}' was not found. "
                           "Install it as described in docs/DETECTION.md (model acquisition).")
        return True, None

    def is_loaded(self) -> bool:
        return self._session is not None

    def load(self) -> None:
        with self._lock:
            if self._session is not None:
                return
            import onnxruntime as ort

            digest = sha256_file(self._path)
            pin = self._settings.detection_model_sha256
            if pin and digest != pin:
                raise ValueError("model file SHA-256 does not match VISTA_DETECTION_MODEL_SHA256")
            options = ort.SessionOptions()
            options.log_severity_level = 3
            if self._settings.detection_threads > 0:
                options.intra_op_num_threads = self._settings.detection_threads
            session = ort.InferenceSession(str(self._path), sess_options=options, providers=["CPUExecutionProvider"])
            self._check_signature(session)
            self._input_name = session.get_inputs()[0].name
            self._sha256 = digest
            self._session = session  # assigned last: a failed load leaves the provider unloaded

    def _check_signature(self, session: Any) -> None:
        inputs, outputs = session.get_inputs(), session.get_outputs()
        if len(inputs) != 1 or not outputs:
            raise ValueError("unexpected model signature (inputs/outputs)")
        shape = list(inputs[0].shape)
        if len(shape) != 4 or shape[1] != 3:
            raise ValueError("model input is not [N, 3, H, W]")
        for dim in shape[2:]:
            if isinstance(dim, int) and dim != self._size:
                raise ValueError("model input size differs from VISTA_DETECTION_INPUT_SIZE")
        out_shape = list(outputs[0].shape)
        if len(out_shape) != 3:
            raise ValueError("model output is not [N, anchors, 5 + classes]")
        if isinstance(out_shape[2], int) and out_shape[2] != 5 + len(self._labels):
            raise ValueError("model class count differs from the label set")
        if isinstance(out_shape[1], int) and out_shape[1] != expected_anchor_count(self._size):
            raise ValueError("model anchor count differs from the configured input size (decoded export?)")

    def unload(self) -> None:
        with self._lock:
            self._session = None
            self._input_name = None
        gc.collect()  # drops the Python references; the OS may not get all native memory back (see docs)

    # -- inference --
    def detect(self, image_rgb: Any, conf_threshold: float, nms_iou: float,
               max_detections: int) -> RawDetectionResult:
        session, name = self._session, self._input_name
        if session is None or name is None:
            raise RuntimeError("detection model is not loaded")
        t0 = time.perf_counter()
        blob, ratio = letterbox_image(image_rgb, self._size, self._settings.detection_resize)
        t1 = time.perf_counter()
        outputs = session.run(None, {name: blob})
        t2 = time.perf_counter()
        import numpy as np

        raw = np.asarray(outputs[0])
        if raw.ndim == 3:
            raw = raw[0]
        boxes, scores, class_ids = postprocess_yolox(raw, self._size, ratio, conf_threshold, nms_iou,
                                                     max_detections, self._settings.detection_nms_mode)
        t3 = time.perf_counter()
        self.last_timings = {"preprocess_ms": (t1 - t0) * 1000, "inference_ms": (t2 - t1) * 1000,
                             "postprocess_ms": (t3 - t2) * 1000}
        found = []
        for box, score, cid in zip(boxes, scores, class_ids):
            cid = int(cid)
            label = self._labels[cid] if 0 <= cid < len(self._labels) else None
            found.append(RawDetection(class_id=cid, confidence=float(score), bbox=[float(v) for v in box], label=label))
        return RawDetectionResult(detections=found)