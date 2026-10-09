"""Data contracts for the OCR MVP. Imports nothing from the rest of the project."""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

SCHEMA_VERSION = "0.2-ocr-mvp"


class VistaError(Exception):
    """Typed error carried across module boundaries. `message` is client-safe."""

    def __init__(self, category: str, code: str, message: str, retryable: bool = False,
                 details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.category = category
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = details or {}


class ErrorInfo(BaseModel):
    category: str
    code: str
    message: str
    retryable: bool = False
    details: Dict[str, Any] = Field(default_factory=dict)


class EngineInfo(BaseModel):
    id: str
    version: Optional[str] = None
    locality: Literal["local", "external"] = "local"


class OCRBlock(BaseModel):
    """One recognized text line/segment, in original-image pixels.

    `bbox2d`, `polygon` and `confidence` are null when the engine did not supply them.
    """

    text: str
    bbox2d: Optional[List[float]] = Field(default=None, description="[x_min, y_min, x_max, y_max]")
    polygon: Optional[List[List[float]]] = None
    confidence: Optional[float] = Field(default=None, description="0..1, null if unavailable")
    line_index: int = 0


class OCRResponse(BaseModel):
    schema_version: str = SCHEMA_VERSION
    request_id: str
    status: Literal["succeeded", "failed", "unavailable"]
    filename: Optional[str] = None
    image_width: Optional[int] = None
    image_height: Optional[int] = None
    coordinate_space: Literal["image_pixels"] = "image_pixels"
    detected_text: str = ""
    blocks: List[OCRBlock] = Field(default_factory=list)
    processing_time_ms: Optional[float] = None
    engine: Optional[EngineInfo] = None
    warnings: List[str] = Field(default_factory=list)
    error: Optional[ErrorInfo] = None
    raw: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Raw engine output; only when include_raw=true"
    )
