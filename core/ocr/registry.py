"""Engine selection by name. To add an engine: implement OCRProvider and register it here."""
from __future__ import annotations

from core.contracts import VistaError
from core.providers import OCRProvider


def create_provider(name: str) -> OCRProvider:
    if name == "rapidocr":
        from .rapidocr_engine import RapidOCRProvider

        return RapidOCRProvider()
    raise VistaError("unavailable", "ENGINE_UNKNOWN", f"Unknown OCR engine '{name}'. Supported: rapidocr.")
