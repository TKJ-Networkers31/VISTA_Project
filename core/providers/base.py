"""Provider interfaces. Engines implement these; orchestration composes them."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Protocol, Tuple

from core.contracts import DetectionModelInfo, EngineInfo


@dataclass
class RawOCRItem:
    """Engine output as given. polygon/confidence are None when the engine has none."""

    text: str
    polygon: Optional[List[List[float]]] = None
    confidence: Optional[float] = None


@dataclass
class RawOCRResult:
    items: List[RawOCRItem] = field(default_factory=list)


class OCRProvider(Protocol):
    def info(self) -> EngineInfo: ...

    def is_available(self) -> Tuple[bool, Optional[str]]:
        """Cheap check (no model load): are the engine's dependencies importable?"""

    def load(self) -> None:
        """Load the model. Called lazily, once. Raise on failure."""

    def is_loaded(self) -> bool: ...

    def recognize(self, image_rgb: Any) -> RawOCRResult:
        """image_rgb: PIL.Image (RGB). Coordinates must be in that image's pixels."""


@dataclass
class RawDetection:
    """One detection as given by a backend, in the pixel space of the image passed to `detect`.

    Nothing here is trusted: orchestration re-validates class, score and box before anything reaches a client.
    """

    class_id: int
    confidence: float
    bbox: List[float]  # [x_min, y_min, x_max, y_max]
    label: Optional[str] = None


@dataclass
class RawDetectionResult:
    detections: List[RawDetection] = field(default_factory=list)


class DetectionProvider(Protocol):
    def info(self) -> EngineInfo: ...

    def model_info(self) -> DetectionModelInfo: ...

    def is_available(self) -> Tuple[bool, Optional[str]]:
        """Cheap check (no model load): dependencies importable and the model file present."""

    def load(self) -> None:
        """Load and validate the model. Called lazily. Raise on failure; `is_loaded` stays False then."""

    def is_loaded(self) -> bool: ...

    def unload(self) -> None:
        """Drop the model reference so its memory can be reclaimed. `is_loaded` must be False afterwards."""

    def detect(self, image_rgb: Any, conf_threshold: float, nms_iou: float, max_detections: int) -> RawDetectionResult:
        """image_rgb: PIL.Image (RGB). Return at most `max_detections` boxes scoring >= `conf_threshold`,
        after non-maximum suppression, in that image's own pixel coordinates."""
