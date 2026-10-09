"""Provider interface for OCR. Engines implement this; orchestration composes them."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Protocol, Tuple

from core.contracts import EngineInfo


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
