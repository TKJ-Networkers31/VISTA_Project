"""Data contract for image understanding (Phase 4): a free-text answer about one image from an EXTERNAL provider.

Not OCR and not detection: no boxes, no coordinates. The `route` block always says where the image went, so a client
(and a test) can prove whether anything left the machine. Imports nothing from the rest of the project except ocr.py.
"""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from .ocr import ErrorInfo

UNDERSTANDING_SCHEMA_VERSION = "0.4-understanding"


class UnderstandingRoute(BaseModel):
    mode: str = Field(max_length=32, description="local_only | hybrid | external_fallback (as requested)")
    target: Literal["local", "external", "none"] = Field(description="'none' = rejected before any processing")
    reason: str = Field(description="stable code: routing reason, or the policy/error code that stopped the request")
    provider: Optional[str] = None
    model: Optional[str] = None
    external_transmission: bool = Field(description="True if an HTTP request carrying the image was attempted")


class UnderstandingResponse(BaseModel):
    schema_version: str = UNDERSTANDING_SCHEMA_VERSION
    request_id: str
    status: Literal["succeeded", "failed", "unavailable"]
    filename: Optional[str] = None
    image_width: Optional[int] = Field(default=None, ge=1)
    image_height: Optional[int] = Field(default=None, ge=1)
    question: Optional[str] = None
    answer: Optional[str] = None
    route: Optional[UnderstandingRoute] = None
    processing_time_ms: Optional[float] = None
    warnings: List[str] = Field(default_factory=list)
    error: Optional[ErrorInfo] = None

    @model_validator(mode="after")
    def _consistent(self) -> "UnderstandingResponse":
        if self.status == "succeeded":
            if self.error is not None:
                raise ValueError("a succeeded response must not carry an error")
            if not self.answer or not self.answer.strip():
                raise ValueError("a succeeded response must carry a non-empty answer")
            if self.route is None or self.route.target == "none":
                raise ValueError("a succeeded response must declare its route")
        else:
            if self.error is None:
                raise ValueError("a failed or unavailable response must carry an error")
            if self.answer is not None:
                raise ValueError("a failed or unavailable response must not carry an answer")
        return self
