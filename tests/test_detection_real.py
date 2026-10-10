"""REAL detection backend (YOLOX via ONNX Runtime). Excluded from the default run.

Run:  python -m pytest -m requires_model -s tests/test_detection_real.py

Needs the model file from docs/DETECTION.md (default models/yolox_nano.onnx, or VISTA_DETECTION_MODEL_PATH).
Like tests/test_real_engine.py these FAIL (not skip) when the backend is missing: they exist to prove it works.
Network is blocked while they run (see conftest), so passing also proves no download is needed at runtime.

Optional ground truth with your own image (no image is committed because none with a clear license is available):
    $env:VISTA_DETECTION_TEST_IMAGE = "C:\\path\\to\\photo.jpg"
    $env:VISTA_DETECTION_TEST_EXPECT = "person,car"      # labels that must appear (comma separated)
"""
import asyncio
import io
import os
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from core.config import Settings, load_dotenv
from core.contracts import DetectionResponse
from core.detection import create_detection_provider
from core.orchestration import DetectionService, ModelManager

pytestmark = pytest.mark.requires_model
ROOT = Path(__file__).resolve().parents[1]


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _synthetic(size=(640, 480)) -> bytes:
    img = Image.new("RGB", size, (180, 190, 200))
    d = ImageDraw.Draw(img)
    d.rectangle([60, 80, 300, 360], fill=(30, 90, 160))
    d.ellipse([340, 120, 560, 340], fill=(200, 60, 40))
    return _png(img)


@pytest.fixture(scope="module")
def service():
    load_dotenv(ROOT / ".env")
    settings = Settings.from_env()
    provider = create_detection_provider(settings)
    ok, reason = provider.is_available()
    assert ok, f"real detection backend required for these tests: {reason}"
    svc = DetectionService(provider, settings, ModelManager(settings.max_resident_models, 30))
    yield svc
    svc.shutdown()


def run(svc, data, **kw):
    return asyncio.run(svc.process(data, "t.png", "image/png", "t", **kw))


def test_real_model_loads_and_reports_identity(service):
    resp = run(service, _synthetic())
    assert resp.status == "succeeded", resp.error
    DetectionResponse.model_validate(resp.model_dump())
    assert service.provider.is_loaded()
    info = service.provider.model_info()
    assert info.sha256 and len(info.sha256) == 64 and info.num_classes == 80
    print(f"\nmodel={info.id} sha256={info.sha256} ms={resp.processing_time_ms} n={len(resp.detections)}")


@pytest.mark.parametrize("size", [(640, 480), (1280, 720), (300, 900), (2000, 1500)])
def test_boxes_are_valid_and_inside_the_original_image(service, size):
    resp = run(service, _synthetic(size), confidence=0.05)  # low threshold: more boxes to check
    assert resp.status == "succeeded" and (resp.image_width, resp.image_height) == size
    for d in resp.detections:
        x1, y1, x2, y2 = d.bbox2d
        assert 0 <= x1 < x2 <= size[0] and 0 <= y1 < y2 <= size[1]
        assert 0 <= d.confidence <= 1 and d.label


def test_results_are_deterministic(service):
    data = _synthetic()
    a, b = run(service, data, confidence=0.05), run(service, data, confidence=0.05)
    assert [d.model_dump() for d in a.detections] == [d.model_dump() for d in b.detections]


def test_blank_image_has_no_detections_at_default_threshold(service):
    resp = run(service, _png(Image.new("RGB", (640, 480), "white")))
    assert resp.status == "succeeded" and resp.detections == []


def test_max_detections_is_respected(service):
    resp = run(service, _synthetic(), confidence=0.0, max_detections=3)
    assert len(resp.detections) <= 3


def test_user_image_contains_expected_labels(service):
    path, expect = os.environ.get("VISTA_DETECTION_TEST_IMAGE"), os.environ.get("VISTA_DETECTION_TEST_EXPECT")
    if not path or not expect:
        pytest.skip("set VISTA_DETECTION_TEST_IMAGE and VISTA_DETECTION_TEST_EXPECT to check real objects")
    data = Path(path).read_bytes()
    mime = "image/png" if path.lower().endswith(".png") else "image/jpeg"
    resp = asyncio.run(service.process(data, Path(path).name, mime, "t_user"))
    assert resp.status == "succeeded", resp.error
    found = {d.label for d in resp.detections}
    print(f"\n{path}: {[(d.label, d.confidence, d.bbox2d) for d in resp.detections]}")
    wanted = {w.strip() for w in expect.split(",") if w.strip()}
    assert wanted <= found, f"missing {wanted - found}; found {sorted(found)}"
