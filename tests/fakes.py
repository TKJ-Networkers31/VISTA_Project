import time
from typing import Optional

from core.contracts import DetectionModelInfo, EngineInfo
from core.providers import RawDetection, RawDetectionResult, RawOCRItem, RawOCRResult


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
        self.unload_calls = 0
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

    def unload(self):
        self.unload_calls += 1
        self._loaded = False

    def recognize(self, image_rgb):
        self.seen_size = image_rgb.size
        if self.gate is not None:
            self.gate.wait(5)
        if self.delay:
            time.sleep(self.delay)
        if self.run_error:
            raise RuntimeError(self.run_error)
        return RawOCRResult(items=list(self.items))


class FakeDetector:
    """Test double for integration tests only. Not evidence that real object detection works."""

    def __init__(self, detections=None, available=True, load_error=None, run_error=None, delay=0.0, gate=None,
                 unload_error=False):
        self.detections = detections if detections is not None else [
            RawDetection(0, 0.60, [10.0, 20.0, 110.0, 80.0], "person"),
            RawDetection(2, 0.90, [50.0, 40.0, 150.0, 90.0], "car"),
        ]
        self.available, self.load_error, self.run_error = available, load_error, run_error
        self.delay, self.gate, self.unload_error = delay, gate, unload_error
        self.load_calls = self.unload_calls = 0
        self.seen_size: Optional[tuple] = None
        self.seen_args: Optional[tuple] = None
        self._loaded = False

    def info(self):
        return EngineInfo(id="fake-detector", version="0", locality="local")

    def model_info(self):
        return DetectionModelInfo(id="fake-model", family="fake", input_size=416, num_classes=80,
                                  sha256=("f" * 64) if self._loaded else None)  # known only after load, like real

    def is_available(self):
        return (True, None) if self.available else (False, "fake detector not installed")

    def is_loaded(self):
        return self._loaded

    def load(self):
        self.load_calls += 1
        if self.load_error:
            raise RuntimeError(self.load_error)
        self._loaded = True

    def unload(self):
        self.unload_calls += 1
        if self.unload_error:
            raise RuntimeError("cannot unload")
        self._loaded = False

    def detect(self, image_rgb, conf_threshold, nms_iou, max_detections):
        self.seen_size = image_rgb.size
        self.seen_args = (conf_threshold, nms_iou, max_detections)
        if self.gate is not None:
            self.gate.wait(5)
        if self.delay:
            time.sleep(self.delay)
        if self.run_error:
            raise RuntimeError(self.run_error)
        return RawDetectionResult(detections=list(self.detections))
