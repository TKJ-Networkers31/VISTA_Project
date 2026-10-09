"""REAL OCR engine on synthetic fixtures. Excluded from the default run.

Run:  python -m pytest -m requires_model -s
These tests fail (not skip) if the engine is missing: they exist to prove the real engine works.
Network is blocked for the duration (see conftest), so passing also proves no download is needed.
"""
import asyncio
import json
from pathlib import Path

import pytest

from core.config import Settings
from core.ocr import create_provider
from core.orchestration import OCRService
from scripts.benchmark_ocr import similarity

FIX = Path(__file__).parent / "fixtures"
MANIFEST = json.loads((FIX / "manifest.json").read_text(encoding="utf-8"))
MIN_SIMILARITY = 0.85  # whitespace/case-insensitive overlap; chosen from a first Linux run (all 1.0), not a target

pytestmark = pytest.mark.requires_model


@pytest.fixture(scope="module")
def service():
    provider = create_provider("rapidocr")
    ok, reason = provider.is_available()
    assert ok, f"real engine required for these tests: {reason}"
    svc = OCRService(provider, Settings())
    yield svc
    svc.shutdown()


def run(svc, name):
    return asyncio.run(svc.process((FIX / name).read_bytes(), name, "image/png", "t"))


@pytest.mark.parametrize("fx", [m for m in MANIFEST if m["expected_lines"]], ids=lambda m: m["file"])
def test_text_fixtures(service, fx):
    resp = run(service, fx["file"])
    print(f"\n{fx['file']}: {resp.detected_text!r} ({resp.processing_time_ms} ms)")
    assert resp.status == "succeeded", resp.error
    assert similarity(fx["expected_lines"], resp.detected_text) >= MIN_SIMILARITY
    for b in resp.blocks:
        x1, y1, x2, y2 = b.bbox2d
        assert 0 <= x1 < x2 <= fx["width"] and 0 <= y1 < y2 <= fx["height"]
        assert b.confidence is None or 0 <= b.confidence <= 1


def test_blank_image_has_no_text(service):
    resp = run(service, "blank.png")
    assert resp.status == "succeeded" and resp.blocks == [] and resp.detected_text == ""


def _iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union else 0.0


def test_large_image_is_downscaled_and_mapped_back(service):
    """Detected boxes must match the ground-truth text boxes in ORIGINAL pixels (not the downscaled copy)."""
    from PIL import ImageFont

    resp = run(service, "large_downscale.png")
    assert any("Downscaled" in w for w in resp.warnings)
    assert (resp.image_width, resp.image_height) == (3000, 2000)
    font = ImageFont.load_default(size=150)  # same font/offsets as scripts/make_fixtures.py
    fx = next(m for m in MANIFEST if m["file"] == "large_downscale.png")
    for i, line in enumerate(fx["expected_lines"]):
        x0, y0, x1, y1 = font.getbbox(line)
        truth = [40 + x0, 30 + i * 240 + y0, 40 + x1, 30 + i * 240 + y1]
        best = max((_iou(truth, b.bbox2d) for b in resp.blocks if b.bbox2d), default=0.0)
        print(f"line {i} {line!r}: best IoU {best:.2f}")
        assert best > 0.5, (line, truth, [b.bbox2d for b in resp.blocks])


def test_model_loaded_once_across_calls(service):
    run(service, "printed_en.png")
    assert service.provider.is_loaded()
