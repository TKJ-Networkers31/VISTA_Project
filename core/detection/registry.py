"""Detection backend selection by name. To add a backend: implement DetectionProvider and register it here."""
from __future__ import annotations

from core.config import DETECTION_BACKENDS, Settings
from core.contracts import VistaError
from core.providers import DetectionProvider


def create_detection_provider(settings: Settings) -> DetectionProvider:
    name = settings.detection_backend
    if name == "yolox-onnx":
        from .yolox_onnx import YoloxOnnxProvider

        return YoloxOnnxProvider(settings)
    raise VistaError("unavailable", "DETECTOR_UNKNOWN",
                     f"Unknown detection backend '{name}'. Supported: {', '.join(DETECTION_BACKENDS)}.")
