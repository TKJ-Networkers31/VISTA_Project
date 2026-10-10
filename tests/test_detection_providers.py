"""Providers, geometry, prompt handling, capabilities, backward compatibility. Fakes only; no model, no network."""
import dataclasses

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from apps.api.main import create_app
from core.config import ConfigError, Settings
from core.detection import create_detection_provider
from core.detection import ultralytics_geometry as ug
from core.detection.open_vocab import OpenVocabularyProvider
from core.providers import RawDetection, RawDetectionResult
from tests.conftest import make_image
from tests.fakes import FakeDetector, FakeOCR

URL = "/api/v1/detection"


class PromptDetector(FakeDetector):
    supports_prompt = True

    def detect(self, image_rgb, conf_threshold, nms_iou, max_detections, prompt=None):
        self.seen_prompt = prompt
        return RawDetectionResult(detections=[RawDetection(0, 0.9, [1.0, 1.0, 50.0, 50.0], prompt or "x")])


def client(detector, **kw):
    s = dataclasses.replace(Settings(), **kw)
    return TestClient(create_app(s, FakeOCR(), detector), raise_server_exceptions=False)


def post(c, **params):
    return c.post(URL, files={"file": ("a.png", make_image(), "image/png")}, params=params)


# ---- letterbox / inverse coordinates
def test_centered_letterbox_roundtrip():
    img = Image.new("RGB", (800, 400), (255, 0, 0))
    blob, ratio, (left, top) = ug.letterbox_centered(img, 640)
    assert blob.shape == (1, 3, 640, 640) and blob.dtype == np.float32 and blob.max() <= 1.0
    assert ratio == pytest.approx(0.8) and left == 0 and top == 160
    assert blob[0, 0, 0, 0] == pytest.approx(114 / 255) and blob[0, 0, 320, 10] == pytest.approx(1.0)  # RGB order
    net = np.array([[80.0, 240.0, 160.0, 320.0]])  # original (100, 100)-(200, 200)
    np.testing.assert_allclose(ug.unmap_boxes(net, ratio, (left, top)), [[100, 100, 200, 200]])


def test_unmap_rejects_bad_ratio():
    with pytest.raises(ValueError):
        ug.unmap_boxes(np.zeros((1, 4)), 0.0, (0, 0))


# ---- end2end decoding, threshold, cap, class mapping
def test_end2end_threshold_cap_and_mapping():
    out = np.array([[10, 10, 50, 50, 0.9, 2], [0, 0, 20, 20, 0.2, 5], [5, 5, 30, 30, 0.6, 0],
                    [1, 1, 2, 2, np.nan, 1]], dtype=np.float32)
    boxes, scores, ids = ug.postprocess_end2end(out, 1.0, (0, 0), 0.3, 10)
    assert ids.tolist() == [2, 0] and scores.tolist() == pytest.approx([0.9, 0.6])
    assert ug.postprocess_end2end(out, 1.0, (0, 0), 0.3, 1)[1].size == 1
    with pytest.raises(ValueError):
        ug.postprocess_end2end(np.zeros((3, 5)), 1.0, (0, 0), 0.3, 5)


# ---- raw decoding + NMS
def test_raw_layout_nms_and_threshold():
    out = np.zeros((4 + 80, 3), np.float32)
    out[0:4, 0] = [50, 50, 40, 40]
    out[4 + 7, 0] = 0.9  # strong box, class 7
    out[0:4, 1] = [52, 52, 40, 40]
    out[4 + 7, 1] = 0.8  # duplicate, same class: suppressed
    out[0:4, 2] = [200, 200, 20, 20]
    out[4 + 3, 2] = 0.1  # below threshold
    boxes, scores, ids = ug.postprocess_raw(out, 0.5, (0, 0), 0.3, 0.45, 10)
    assert ids.tolist() == [7] and scores.tolist() == pytest.approx([0.9])
    np.testing.assert_allclose(boxes[0], [60, 60, 140, 140])  # (30..70) / 0.5


# ---- provider selection / config / capabilities
def test_registry_selects_backends_and_rejects_unknown():
    for name, cls in [("yolox-onnx", "YoloxOnnxProvider"), ("yolox_nano", "YoloxOnnxProvider"),
                      ("yolo26n_onnx", "Yolo26OnnxProvider"), ("open_vocabulary", "OpenVocabularyProvider")]:
        assert type(create_detection_provider(dataclasses.replace(Settings(), detection_backend=name))).__name__ == cls
    with pytest.raises(ConfigError):
        Settings.from_env({"VISTA_DETECTION_BACKEND": "nope"})
    assert Settings.from_env({"VISTA_DETECTION_BACKEND": "yolo26n_onnx"}).detection_backend == "yolo26n_onnx"


def test_yolo26_without_model_file_is_unavailable(tmp_path):
    s = dataclasses.replace(Settings(), detection_backend="yolo26n_onnx", detection_model_path=str(tmp_path / "x.onnx"))
    c = TestClient(create_app(s, FakeOCR()), raise_server_exceptions=False)
    cap = c.get("/api/v1/detection/capabilities").json()["detection"]
    assert cap["status"] == "unavailable" and cap["family"] == "yolo26" and cap["supports_prompt"] is False
    assert post(c).status_code == 503


def test_open_vocabulary_is_honestly_unsupported():
    s = dataclasses.replace(Settings(), detection_backend="open_vocabulary")
    c = TestClient(create_app(s, FakeOCR()), raise_server_exceptions=False)
    cap = c.get("/api/v1/detection/capabilities").json()["detection"]
    assert cap["status"] == "unavailable" and cap["supported"] is False and cap["experimental"] is True
    assert cap["supports_prompt"] is True and "not supported" in cap["reason"]
    r = post(c, prompt="a red cup")
    assert r.status_code == 503 and r.json()["detections"] == []
    assert OpenVocabularyProvider().is_available()[0] is False


# ---- prompt handling + backward compatibility
def test_prompt_rejected_when_backend_does_not_support_it():
    c = client(FakeDetector())
    r = post(c, prompt="a cup")
    assert r.status_code == 400 and r.json()["error"]["code"] == "PROMPT_NOT_SUPPORTED"


@pytest.mark.parametrize("prompt", ["", "   ", "x" * 201, "bad\x01char"])
def test_invalid_prompts(prompt):
    r = post(client(PromptDetector()), prompt=prompt)
    assert r.status_code == 400 and r.json()["error"]["code"] == "INVALID_PARAMETER"


def test_prompt_reaches_a_supporting_backend_and_is_echoed():
    det = PromptDetector()
    body = post(client(det), prompt="  red cup ").json()
    assert body["status"] == "succeeded" and det.seen_prompt == "red cup"
    assert body["parameters"]["prompt"] == "red cup" and body["detections"][0]["label"] == "red cup"


def test_requests_without_prompt_are_unchanged():
    det = FakeDetector()
    body = post(client(det), confidence="0.5").json()
    assert body["schema_version"] == "0.3-detection" and body["parameters"]["prompt"] is None
    assert det.seen_args[0] == 0.5