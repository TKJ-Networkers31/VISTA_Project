"""RapidOCR (ONNX Runtime, CPU) provider. Model files ship inside the wheel."""
from __future__ import annotations

import importlib.util
from importlib import metadata
from typing import Optional, Tuple

from core.contracts import EngineInfo
from core.providers import RawOCRItem, RawOCRResult

_MODULE = "rapidocr_onnxruntime"


def _to_float(value) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class RapidOCRProvider:
    def __init__(self) -> None:
        self._engine = None

    def info(self) -> EngineInfo:
        try:
            version = metadata.version("rapidocr-onnxruntime")
        except metadata.PackageNotFoundError:
            version = None
        return EngineInfo(id="rapidocr-onnxruntime", version=version, locality="local")

    def is_available(self) -> Tuple[bool, Optional[str]]:
        if importlib.util.find_spec(_MODULE) is None:
            return False, "Package 'rapidocr-onnxruntime' is not installed (pip install rapidocr-onnxruntime)."
        return True, None

    def is_loaded(self) -> bool:
        return self._engine is not None

    def load(self) -> None:
        if self._engine is None:
            from rapidocr_onnxruntime import RapidOCR  # heavy import, deferred on purpose

            self._engine = RapidOCR()

    def unload(self) -> None:
        """Drop the engine so its memory can be reclaimed (the OS may keep part of it; see docs/DETECTION.md)."""
        import gc

        self._engine = None
        gc.collect()

    def recognize(self, image_rgb) -> RawOCRResult:
        import numpy as np

        arr = np.asarray(image_rgb)[:, :, ::-1].copy()  # RapidOCR expects BGR
        result, _elapsed = self._engine(arr)
        items = []
        for entry in result or []:
            box, text, score = entry[0], entry[1], entry[2]
            polygon = [[float(x), float(y)] for x, y in box] if box is not None else None
            items.append(RawOCRItem(text=str(text), polygon=polygon, confidence=_to_float(score)))
        return RawOCRResult(items=items)
