"""YOLO26n (Ultralytics ONNX export, ONNX Runtime CPU) provider. The model file is never downloaded implicitly.

Fails closed: the output signature must match a known layout, otherwise load() raises. NOT verified against a real
exported file in the build environment (see docs/DETECTION_PROVIDERS.md).
"""
from __future__ import annotations

import ast
import gc
import importlib.util
import threading
import time
from importlib import metadata
from typing import Any, Dict, Optional, Tuple

from core.config import Settings
from core.contracts import DetectionModelInfo, EngineInfo
from core.providers import RawDetection, RawDetectionResult

from . import ultralytics_geometry as ug
from .coco_labels import COCO_CLASSES
from .ort_options import build_session_options
from .yolox_onnx import resolve_model_path, sha256_file


class Yolo26OnnxProvider:
    supports_prompt = False

    def __init__(self, settings: Settings, labels: Tuple[str, ...] = COCO_CLASSES) -> None:
        self._settings = settings
        self._labels = tuple(labels)
        self._path = resolve_model_path(settings.detection_model_path)
        self._size = settings.detection_input_size
        self._session: Any = None
        self._input_name: Optional[str] = None
        self._layout: Optional[str] = None
        self._sha256: Optional[str] = None
        self._lock = threading.Lock()
        self.last_timings: Dict[str, float] = {}

    def info(self) -> EngineInfo:
        try:
            version = metadata.version("onnxruntime")
        except metadata.PackageNotFoundError:
            version = None
        return EngineInfo(id="onnxruntime", version=version, locality="local")

    def model_info(self) -> DetectionModelInfo:
        return DetectionModelInfo(id=self._settings.detection_model_id, family="yolo26", input_size=self._size,
                                  num_classes=len(self._labels), sha256=self._sha256)

    def describe(self) -> Dict[str, Any]:
        return {"family": "yolo26", "supported": True, "experimental": False,
                "classes": {"count": len(self._labels), "source": "COCO (or the model's own metadata names)"},
                "runtime": "onnxruntime CPUExecutionProvider", "layout": self._layout,
                "license": "Ultralytics weights: AGPL-3.0 or Enterprise (owner decision, see DETECTION.md)",
                "limitations": ["output layout verified at load time only", "closed vocabulary", "CPU only"]}

    def is_available(self) -> Tuple[bool, Optional[str]]:
        for module in ("numpy", "onnxruntime"):
            if importlib.util.find_spec(module) is None:
                return False, f"Package '{module}' is not installed (pip install onnxruntime numpy)."
        if not self._path.is_file():
            return False, (f"Detection model file '{self._path.name}' was not found. "
                           "Export it as described in docs/DETECTION_PROVIDERS.md.")
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
            options = build_session_options(ort, self._settings.detection_threads)
            session = ort.InferenceSession(str(self._path), sess_options=options, providers=["CPUExecutionProvider"])
            labels = self._labels_from_metadata(session) or self._labels
            layout = self._check_signature(session, len(labels))
            self._labels, self._layout = labels, layout
            self._input_name = session.get_inputs()[0].name
            self._sha256 = digest
            self._session = session

    @staticmethod
    def _labels_from_metadata(session: Any) -> Optional[Tuple[str, ...]]:
        try:
            raw = session.get_modelmeta().custom_metadata_map.get("names")
            names = ast.literal_eval(raw) if raw else None
        except Exception:
            return None
        if isinstance(names, dict) and names and sorted(names) == list(range(len(names))):
            return tuple(str(names[i]) for i in range(len(names)))
        return None

    def _check_signature(self, session: Any, num_classes: int) -> str:
        inputs, outputs = session.get_inputs(), session.get_outputs()
        if len(inputs) != 1 or not outputs:
            raise ValueError("unexpected model signature (inputs/outputs)")
        shape = list(inputs[0].shape)
        if len(shape) != 4 or shape[1] != 3:
            raise ValueError("model input is not [N, 3, H, W]")
        for dim in shape[2:]:
            if isinstance(dim, int) and dim != self._size:
                raise ValueError("model input size differs from VISTA_DETECTION_INPUT_SIZE")
        out = list(outputs[0].shape)
        if len(out) != 3:
            raise ValueError("unsupported output rank (expected [1, 4+C, A] or [1, N, 6])")
        if isinstance(out[1], int) and out[1] == 4 + num_classes:
            return "raw"
        if isinstance(out[2], int) and out[2] == 6:
            return "end2end"
        raise ValueError("unsupported output layout; neither [1, 4+C, A] nor [1, N, 6]")

    def unload(self) -> None:
        with self._lock:
            self._session = None
            self._input_name = None
        gc.collect()

    def detect(self, image_rgb: Any, conf_threshold: float, nms_iou: float,
               max_detections: int) -> RawDetectionResult:
        session, name, layout = self._session, self._input_name, self._layout
        if session is None or name is None or layout is None:
            raise RuntimeError("detection model is not loaded")
        import numpy as np

        t0 = time.perf_counter()
        blob, ratio, pad = ug.letterbox_centered(image_rgb, self._size)
        t1 = time.perf_counter()
        out = np.asarray(session.run(None, {name: blob})[0])[0]
        t2 = time.perf_counter()
        if layout == "end2end":
            boxes, scores, ids = ug.postprocess_end2end(out, ratio, pad, conf_threshold, max_detections)
        else:
            boxes, scores, ids = ug.postprocess_raw(out, ratio, pad, conf_threshold, nms_iou, max_detections,
                                                    self._settings.detection_nms_mode == "class_aware")
        t3 = time.perf_counter()
        self.last_timings = {"preprocess_ms": (t1 - t0) * 1000, "inference_ms": (t2 - t1) * 1000,
                             "postprocess_ms": (t3 - t2) * 1000}
        found = []
        for box, score, cid in zip(boxes, scores, ids, strict=True):
            cid = int(cid)
            label = self._labels[cid] if 0 <= cid < len(self._labels) else None
            found.append(RawDetection(class_id=cid, confidence=float(score), bbox=[float(v) for v in box],
                                      label=label))
        return RawDetectionResult(detections=found)