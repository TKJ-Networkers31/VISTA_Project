import asyncio
import dataclasses
import io
import tempfile
import threading
import time

import numpy as np
import pytest
from PIL import Image

from core.config import ConfigError, Settings
from core.contracts import OCRResponse
from core.orchestration import OCRService
from tests.conftest import make_image, post
from tests.fakes import FakeOCR


# 1. health ---------------------------------------------------------------
def test_health(make_client):
    c, _ = make_client()
    r = c.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok" and r.json()["capabilities"]["ocr"]["status"] == "available"


def test_capabilities(make_client):
    c, _ = make_client()
    body = c.get("/api/v1/ocr/capabilities").json()
    assert body["limits"]["max_upload_bytes"] == 10_485_760 and body["queue"]["capacity"] == 5


# 2. valid upload + 7. contract ---------------------------------------------
def test_valid_upload_contract_and_order(make_client):
    c, _ = make_client()
    r = post(c, make_image())
    assert r.status_code == 200
    body = r.json()
    OCRResponse.model_validate(body)
    for key in ("request_id", "status", "filename", "image_width", "image_height", "detected_text", "blocks",
                "processing_time_ms", "engine", "warnings", "error"):
        assert key in body
    assert body["status"] == "succeeded" and body["filename"] == "a.png"
    assert (body["image_width"], body["image_height"]) == (200, 100)
    assert body["detected_text"] == "Hello World\nSecond line"  # fake returned them out of order
    assert body["blocks"][0]["bbox2d"] == [10.0, 10.0, 55.0, 30.0]
    assert body["error"] is None and body["raw"] is None


def test_unknown_confidence_stays_null(make_client):
    c, _ = make_client()
    blocks = post(c, make_image()).json()["blocks"]
    second = next(b for b in blocks if b["text"] == "Second line")
    assert second["confidence"] is None  # never invented


def test_include_raw(make_client):
    c, _ = make_client()
    assert len(post(c, make_image(), include_raw="true").json()["raw"]) == 3


def test_no_coordinates_from_engine(make_client):
    from core.providers import RawOCRItem
    c, _ = make_client(FakeOCR(items=[RawOCRItem("only text")]))
    body = post(c, make_image()).json()
    assert body["blocks"][0]["bbox2d"] is None and body["blocks"][0]["polygon"] is None
    assert any("without coordinates" in w for w in body["warnings"])


# 3. no text ---------------------------------------------------------------
def test_image_without_text(make_client):
    c, _ = make_client(FakeOCR(items=[]))
    body = post(c, make_image()).json()
    assert body["status"] == "succeeded" and body["blocks"] == [] and body["detected_text"] == ""
    assert any("No text" in w for w in body["warnings"])


# 4. corrupt / unsupported / empty ------------------------------------------
def test_corrupt_file(make_client):
    c, _ = make_client()
    r = post(c, make_image()[:60])
    assert r.status_code == 400 and r.json()["error"]["code"] == "CORRUPT_IMAGE"


def test_unsupported_content(make_client):
    c, _ = make_client()
    r = post(c, b"just some text, not an image", "x.png", "image/png")
    assert r.status_code == 415 and r.json()["error"]["code"] == "UNSUPPORTED_FORMAT"


def test_unsupported_real_format_gif(make_client):
    c, _ = make_client()
    r = post(c, make_image("GIF"), "a.gif", "image/png")  # lying MIME, real GIF
    assert r.status_code == 415


def test_unsupported_declared_mime(make_client):
    c, _ = make_client()
    r = post(c, make_image(), "a.txt", "text/plain")
    assert r.status_code == 415


def test_empty_file(make_client):
    c, _ = make_client()
    r = post(c, b"")
    assert r.status_code == 400 and r.json()["error"]["code"] == "EMPTY_FILE"


def test_missing_file_field(make_client):
    c, _ = make_client()
    r = c.post("/api/v1/ocr", data={"x": "y"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "MISSING_FILE"


# 5. limits -----------------------------------------------------------------
def test_oversize_bytes_service_check(make_client):
    c, _ = make_client(max_upload_bytes=1000)
    r = post(c, make_image(size=(300, 300), color="red") + b"0" * 2000)
    assert r.status_code == 413 and r.json()["error"]["code"] == "IMAGE_TOO_LARGE"


def test_oversize_bytes_rejected_before_parsing(make_client):
    c, _ = make_client(max_upload_bytes=1000)
    r = post(c, b"0" * 200_000)
    assert r.status_code == 413 and r.json()["error"]["details"]["limit_bytes"] == 1000


def test_pixel_limit(make_client):
    c, _ = make_client(max_image_pixels=1000)
    r = post(c, make_image(size=(100, 100)))
    assert r.status_code == 413 and r.json()["error"]["code"] == "IMAGE_DIMENSIONS_EXCEEDED"


def test_side_limit(make_client):
    c, _ = make_client(max_image_side=50)
    assert post(c, make_image(size=(100, 10))).status_code == 413


# 6. engine failures ---------------------------------------------------------
def test_engine_not_installed(make_client):
    c, _ = make_client(FakeOCR(available=False))
    r = post(c, make_image())
    assert r.status_code == 503 and r.json()["status"] == "unavailable"
    assert r.json()["error"]["code"] == "ENGINE_UNAVAILABLE" and r.json()["detected_text"] == ""


def test_engine_load_failure_hides_internal_text(make_client):
    c, _ = make_client(FakeOCR(load_error="C:\\secret\\path\\model.onnx missing"))
    r = post(c, make_image())
    assert r.status_code == 503 and r.json()["error"]["code"] == "ENGINE_LOAD_FAILED"
    assert "secret" not in r.text


def test_engine_runtime_error(make_client):
    c, _ = make_client(FakeOCR(run_error="boom /etc/passwd"))
    r = post(c, make_image())
    assert r.status_code == 500 and r.json()["error"]["code"] == "ENGINE_FAILED" and "passwd" not in r.text


def test_model_loaded_once(make_client):
    c, eng = make_client()
    post(c, make_image())
    post(c, make_image())
    assert eng.load_calls == 1


# 9. backend error handling ---------------------------------------------------
def test_unhandled_error_is_structured(make_client, monkeypatch):
    c, _ = make_client()

    async def boom(*a, **k):
        raise KeyError("secret")

    monkeypatch.setattr(c.app.state.service, "process", boom)
    r = post(c, make_image())
    assert r.status_code == 500 and r.json()["error"]["code"] == "INTERNAL_ERROR" and "secret" not in r.text


def test_filename_sanitized(make_client):
    c, _ = make_client()
    assert post(c, make_image(), "..\\..\\evil/../pic.png").json()["filename"] == "pic.png"


# downscale mapping ------------------------------------------------------------
def test_downscale_maps_back_to_original_pixels(make_client):
    from core.providers import RawOCRItem
    eng = FakeOCR(items=[RawOCRItem("X", [[10, 10], [50, 10], [50, 30], [10, 30]], 0.8)])
    c, _ = make_client(eng, ocr_max_side=100)
    body = post(c, make_image(size=(400, 200))).json()
    assert eng.seen_size == (100, 50)
    assert body["blocks"][0]["bbox2d"] == [40.0, 40.0, 200.0, 120.0]
    assert any("Downscaled" in w for w in body["warnings"])


# 8. temp file cleanup -----------------------------------------------------------
def test_no_temp_files_left(make_client, tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    rng = np.random.default_rng(0)
    noisy = io.BytesIO()
    Image.fromarray(rng.integers(0, 255, (700, 700, 3), dtype=np.uint8)).save(noisy, "PNG")
    assert len(noisy.getvalue()) > 1_048_576  # forces Starlette to spool to disk
    c, _ = make_client()
    assert post(c, noisy.getvalue()).status_code == 200
    assert list(tmp_path.iterdir()) == []


# concurrency / timeout ------------------------------------------------------------
def test_backpressure_rejects_when_full():
    gate = threading.Event()
    svc = OCRService(FakeOCR(gate=gate), dataclasses.replace(Settings(), worker_concurrency=1, queue_max_size=0))

    async def scenario():
        first = asyncio.create_task(svc.process(make_image(), "a", "image/png", "r1"))
        await asyncio.sleep(0.2)
        second = await svc.process(make_image(), "b", "image/png", "r2")
        gate.set()
        return second, await first

    second, first = asyncio.run(scenario())
    assert second.error.code == "QUEUE_FULL" and second.error.category == "resource_limit"
    assert first.status == "succeeded" and svc.inflight == 0


def test_timeout_then_slot_released():
    svc = OCRService(FakeOCR(delay=0.5), dataclasses.replace(Settings(), task_timeout_seconds=1))
    svc.settings = dataclasses.replace(svc.settings, task_timeout_seconds=0.1)  # sub-second for the test
    resp = asyncio.run(svc.process(make_image(), "a", "image/png", "r1"))
    assert resp.error.code == "TASK_TIMEOUT"
    deadline = time.time() + 3
    while svc.inflight and time.time() < deadline:
        time.sleep(0.05)
    assert svc.inflight == 0


# config ----------------------------------------------------------------------------
def test_config_validation_names_variable_not_value():
    with pytest.raises(ConfigError) as e:
        Settings.from_env({"VISTA_PORT": "abc-secret"})
    assert "VISTA_PORT" in str(e.value) and "secret" not in str(e.value)


# 10. UI served and wired -------------------------------------------------------------
def test_ui_served_and_wired(make_client):
    c, _ = make_client()
    html = c.get("/").text
    js = c.get("/static/app.js").text
    assert c.get("/static/style.css").status_code == 200
    ids = ["file-input", "run-btn", "clear-btn", "copy-btn", "loading", "error", "preview", "overlay",
           "text-out", "blocks", "engine-status", "meta"]
    for i in ids:
        assert f'id="{i}"' in html, i
    for i in ["file-input", "run-btn", "clear-btn", "copy-btn", "text-out", "overlay"]:
        assert f'$("{i}")' in js, i  # element is actually used by the script
    assert "/api/v1/ocr" in js and "/api/v1/ocr/capabilities" in js


# real engine (excluded from default runs) ----------------------------------------------
@pytest.mark.requires_model
def test_real_engine_on_generated_image():
    from PIL import ImageDraw, ImageFont

    from core.ocr import create_provider
    img = Image.new("RGB", (800, 300), "white")
    d = ImageDraw.Draw(img)
    f = ImageFont.load_default(size=60)
    d.text((30, 30), "VISTA OCR TEST", fill="black", font=f)
    d.text((30, 150), "Line two 12345", fill="black", font=f)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    s = Settings()
    svc = OCRService(create_provider("rapidocr"), s)
    resp = asyncio.run(svc.process(buf.getvalue(), "gen.png", "image/png", "r_real"))
    print("REAL OCR:", repr(resp.detected_text), resp.processing_time_ms, "ms")
    assert resp.status == "succeeded"
    assert "VISTA" in resp.detected_text.upper() and "12345" in resp.detected_text
