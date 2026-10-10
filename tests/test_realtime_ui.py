"""Realtime page: static wiring, and the frame path through the EXISTING detection endpoint. Fake providers only.

These tests do not prove that a browser, a webcam or real detection works. Camera/browser behavior is covered by
tests/js/realtime_core.test.js (logic, fakes) and the manual procedure in docs/REALTIME.md.
"""
import re
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.api.main import create_app
from core.config import Settings
from core.contracts import DetectionResponse
from tests.conftest import make_image, post
from tests.fakes import FakeDetector, FakeOCR

STATIC = Path(__file__).resolve().parents[1] / "apps" / "web" / "static"
URL = "/api/v1/detection"


@pytest.fixture
def client():
    det = FakeDetector()
    return TestClient(create_app(Settings(), FakeOCR(), det), raise_server_exceptions=False), det


def frame(client, data=None, **params):
    data = data if data is not None else make_image("JPEG", size=(640, 360))
    return client.post(URL, files={"file": ("frame.jpg", data, "image/jpeg")}, params=params)


# ---- static wiring ---------------------------------------------------------------------------------
def test_realtime_assets_are_served(client):
    c, _ = client
    for name in ("realtime.html", "realtime.js", "realtime_core.js", "realtime.css"):
        assert c.get(f"/static/{name}").status_code == 200, name


def test_every_element_used_by_the_script_exists_in_the_page():
    html = (STATIC / "realtime.html").read_text(encoding="utf-8")
    js = (STATIC / "realtime.js").read_text(encoding="utf-8")
    used = set(re.findall(r'\$\("([\w-]+)"\)', js)) | {"video", "rt-overlay", "rt-stage"}
    for ident in used:
        assert f'id="{ident}"' in html, ident


def test_realtime_script_uses_only_existing_endpoints_and_stores_nothing():
    js = (STATIC / "realtime.js").read_text(encoding="utf-8")
    core = (STATIC / "realtime_core.js").read_text(encoding="utf-8")
    assert "/api/v1/detection" in js and "/api/v1/detection/capabilities" in js
    for forbidden in ("WebSocket", "localStorage", "sessionStorage", "indexedDB", "eval(", "innerHTML"):
        assert forbidden not in js and forbidden not in core, forbidden
    assert "http://" not in js and "https://" not in js  # nothing is sent to an external host
    assert js.count("getUserMedia") == 1  # only the availability check; the call lives in the controller


def test_index_links_to_realtime_and_keeps_ocr_ids(client):
    c, _ = client
    html = c.get("/").text
    assert "/static/realtime.html" in html
    for ident in ("file-input", "run-btn", "clear-btn", "copy-btn", "text-out", "overlay", "blocks"):
        assert f'id="{ident}"' in html, ident


# ---- frame path through the existing endpoint ------------------------------------------------------
def test_jpeg_frame_with_confidence_override_returns_the_documented_contract(client):
    c, det = client
    r = frame(c, confidence="0.5")
    assert r.status_code == 200
    body = r.json()
    DetectionResponse.model_validate(body)
    assert (body["image_width"], body["image_height"]) == (640, 360)
    assert det.seen_args[0] == 0.5 and det.seen_size == (640, 360)
    assert all(d["bbox2d"][2] <= 640 and d["bbox2d"][3] <= 360 for d in body["detections"])


def test_ui_relevant_failures_keep_the_detection_shape():
    c = TestClient(create_app(Settings(), FakeOCR(), FakeDetector(available=False)), raise_server_exceptions=False)
    r = frame(c)
    body = r.json()
    assert r.status_code == 503 and body["status"] == "unavailable" and body["error"]["code"] == "DETECTOR_UNAVAILABLE"
    assert body["detections"] == []


def test_many_sequential_frames_leak_no_slots_and_load_the_model_once(client):
    c, det = client
    for _ in range(12):
        assert frame(c).status_code == 200
    assert c.app.state.detection_service.inflight == 0 and det.load_calls == 1


def test_frames_are_not_written_to_disk(client, tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    c, _ = client
    assert frame(c).status_code == 200
    assert list(tmp_path.iterdir()) == []


def test_ocr_still_works_next_to_realtime_traffic(client):
    c, _ = client
    assert frame(c).status_code == 200
    r = post(c, make_image())
    assert r.status_code == 200 and r.json()["schema_version"] == "0.2-ocr-mvp"
