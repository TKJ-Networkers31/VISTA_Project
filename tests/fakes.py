import time
from typing import Optional

from core.contracts import EngineInfo
from core.providers import RawOCRItem, RawOCRResult


class FakeOCR:
    """Test double for integration tests only. Not evidence that real OCR works."""

    def __init__(self, items=None, available=True, load_error=None, run_error=None, delay=0.0, gate=None):
        self.items = items if items is not None else [
            RawOCRItem("World", [[60, 10], [110, 10], [110, 30], [60, 30]], 0.9),
            RawOCRItem("Second line", [[10, 50], [120, 50], [120, 70], [10, 70]], None),
            RawOCRItem("Hello", [[10, 10], [55, 10], [55, 30], [10, 30]], 0.95),
        ]
        self.available, self.load_error, self.run_error = available, load_error, run_error
        self.delay, self.gate = delay, gate
        self.load_calls = 0
        self.seen_size: Optional[tuple] = None
        self._loaded = False

    def info(self):
        return EngineInfo(id="fake", version="0", locality="local")

    def is_available(self):
        return (True, None) if self.available else (False, "fake engine not installed")

    def is_loaded(self):
        return self._loaded

    def load(self):
        self.load_calls += 1
        if self.load_error:
            raise RuntimeError(self.load_error)
        self._loaded = True

    def recognize(self, image_rgb):
        self.seen_size = image_rgb.size
        if self.gate is not None:
            self.gate.wait(5)
        if self.delay:
            time.sleep(self.delay)
        if self.run_error:
            raise RuntimeError(self.run_error)
        return RawOCRResult(items=list(self.items))
