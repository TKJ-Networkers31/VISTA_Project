"""Data contracts for object detection (Phase 3). Imports nothing from the rest of the project.

Boxes are `[x_min, y_min, x_max, y_max]` in ORIGINAL image pixels (origin top-left, x right, y down).
Everything that reaches a client is validated here, so a backend bug cannot leak NaN, inverted or
out-of-image boxes through the API.
"""
from __future__ import annotations

import math
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from .ocr import EngineInfo, ErrorInfo

DETECTION_SCHEMA_VERSION = "0.3-detection"


class Detection(BaseModel):
    """One detected object. `confidence` is the backend's score (YOLOX: objectness x class probability)."""

    class_id: int = Field(ge=0, description="Index into the model's label set")
    label: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    bbox2d: List[float] = Field(description="[x_min, y_min, x_max, y_max] in original image pixels")

    @field_validator("bbox2d")
    @classmethod
    def _valid_box(cls, value: List[float]) -> List[float]:
        if len(value) != 4:
            raise ValueError("bbox2d must contain exactly 4 numbers")
        if not all(math.isfinite(v) for v in value):
            raise ValueError("bbox2d must contain only finite numbers")
        x1, y1, x2, y2 = value
        if x1 < 0 or y1 < 0:
            raise ValueError("bbox2d must not have negative coordinates")
        if x2 <= x1 or y2 <= y1:
            raise ValueError("bbox2d must satisfy x_max > x_min and y_max > y_min")
        return value


class DetectionModelInfo(BaseModel):
    id: str
    family: Optional[str] = None
    input_size: Optional[int] = None
    num_classes: Optional[int] = None
    sha256: Optional[str] = Field(default=None, description="SHA-256 of the model file, known after the model loaded")


class DetectionParameters(BaseModel):
    """The values actually applied to this request (defaults or per-request overrides)."""

    confidence_threshold: float = Field(ge=0.0, le=1.0)
    nms_iou_threshold: float = Field(ge=0.0, le=1.0)
    max_detections: int = Field(ge=1)
    input_size: Optional[int] = None


class DetectionResponse(BaseModel):
    schema_version: str = DETECTION_SCHEMA_VERSION
    request_id: str
    status: Literal["succeeded", "failed", "unavailable"]
    filename: Optional[str] = None
    image_width: Optional[int] = Field(default=None, ge=1)
    image_height: Optional[int] = Field(default=None, ge=1)
    coordinate_space: Literal["image_pixels"] = "image_pixels"
    bbox_format: Literal["xyxy"] = "xyxy"
    detections: List[Detection] = Field(default_factory=list)
    processing_time_ms: Optional[float] = None
    engine: Optional[EngineInfo] = None
    model: Optional[DetectionModelInfo] = None
    parameters: Optional[DetectionParameters] = None
    warnings: List[str] = Field(default_factory=list)
    error: Optional[ErrorInfo] = None

    @model_validator(mode="after")
    def _consistent(self) -> "DetectionResponse":
        if self.status == "succeeded":
            if self.error is not None:
                raise ValueError("a succeeded response must not carry an error")
            if self.image_width is None or self.image_height is None:
                raise ValueError("a succeeded response must declare image_width and image_height")
            for det in self.detections:
                if det.bbox2d[2] > self.image_width or det.bbox2d[3] > self.image_height:
                    raise ValueError("a detection lies outside the image")
        else:
            if self.error is None:
                raise ValueError("a failed or unavailable response must carry an error")
            if self.detections:
                raise ValueError("a failed or unavailable response must not carry detections")
        return self
