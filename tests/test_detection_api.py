"""Detection API, orchestration, capabilities, lifecycle and OCR regression. Fake providers only.

These tests prove the plumbing (contract, errors, coordinates, limits, lifecycle). They are NOT evidence that real
object detection works: that is tests/test_detection_real.py (marker requires_model).
"""
import asyncio
import dataclasses
import threading
import time

import pytest
from fastapi.testclient import TestClient

from apps.api.main import create_app
from core.config import Settings
from core.contracts import DetectionResponse, VistaError
from core.orchestration import DetectionService, ModelManager, OCRService
from core.providers import RawDetection
from tests.conftest import make_image, post
from tests.fakes import FakeDetector, FakeOCR

URL = "/api/v1/detection"


@pytest.fixture
def make_det_client():
    def _make(detector=None, ocr=None, **overrides):
        s = dataclasses.replace(Settings(), **overrides)
        detector = detector or FakeDetector()
        ocr = ocr or FakeOCR()
        return TestClient(create_app(s, ocr, detector), raise_server_exceptions=False), detector, ocr

    return _make


def dpost(client, data, name="a.png", mime="image/png", **params):
    return client.post(URL, files={"file": (name, data, mime)}, params=params)


# ---- 10: API success ---------------------------------------------------------------------------
def test_success_contract_and_order(make_det_client):
    c, det, _ = make_det_client()
    r = dpost(c, make_image(size=(200, 100)))
    assert r.status_code == 200
    body = r.json()
    DetectionResponse.model_validate(body)
    assert body["status"] == "succeeded" and body["filename"] == "a.png"
    assert (body["image_width"], body["image_height"]) == (200, 100)
    assert body["coordinate_space"] == "image_pixels" and body["bbox_format"] == "xyxy"
    assert [d["label"] for d in body["detections"]] == ["car", "person"]  # sorted by confidence
    assert body["detections"][0] == {"class_id": 2, "label": "car", "confidence": 0.9,
                                     "bbox2d": [50.0, 40.0, 150.0, 90.0]}
    assert body["engine"]["id"] == "fake-detector" and body["model"]["id"] == "fake-model"
    assert body["parameters"] == {"confidence_threshold": 0.3, "nms_iou_threshold": 0.45, "max_detections": 100,
                                "input_size": 416, "prompt": None}
    assert body["error"] is None and det.seen_size == (200, 100)  # backend sees the ORIGINAL image


def test_empty_detections_succeed_with_warning(make_det_client):
    c, _, _ = make_det_client(FakeDetector(detections=[]))
    body = dpost(c, make_image()).json()
    assert body["status"] == "succeeded" and body["detections"] == []
    assert any("No objects" in w for w in body["warnings"])


def test_backend_boxes_are_clipped_and_bad_ones_dropped(make_det_client):
    bad = [RawDetection(0, 0.8, [-20.0, -20.0, 5000.0, 5000.0], "person"),
           RawDetection(1, float("nan"), [1.0, 1.0, 5.0, 5.0], "bicycle"),
           RawDetection(1, 0.7, [9.0, 9.0, 3.0, 3.0], "bicycle")]
    c, _, _ = make_det_client(FakeDetector(detections=bad))
    body = dpost(c, make_image(size=(200, 100))).json()
    assert body["status"] == "succeeded"
    assert [d["bbox2d"] for d in body["detections"]] == [[0.0, 0.0, 200.0, 100.0]]
    assert any("2 backend detection(s)" in w for w in body["warnings"])


def test_request_overrides_can_only_be_stricter(make_det_client):
    c, det, _ = make_det_client(detection_max_detections=5)
    body = dpost(c, make_image(), confidence="0.8", max_detections="2").json()
    assert det.seen_args == (0.8, 0.45, 2) and body["parameters"]["max_detections"] == 2
    dpost(c, make_image(), max_detections="99")
    assert det.seen_args[2] == 5  # capped at the configured maximum


def test_max_detections_caps_the_result(make_det_client):
    many = [RawDetection(0, 0.5 + i / 100, [1.0 + i, 1.0, 20.0 + i, 20.0], "person") for i in range(10)]
    c, _, _ = make_det_client(FakeDetector(detections=many), detection_max_detections=3)
    assert len(dpost(c, make_image()).json()["detections"]) == 3


@pytest.mark.parametrize("params", [{"confidence": "1.5"}, {"confidence": "-0.1"}, {"confidence": "abc"},
                                    {"confidence": "nan"}, {"max_detections": "0"}])
def test_invalid_parameters(make_det_client, params):
    c, det, _ = make_det_client()
    r = dpost(c, make_image(), **params)
    assert r.status_code == 400 and r.json()["error"]["code"] == "INVALID_PARAMETER"
    DetectionResponse.model_validate(r.json())
    assert det.load_calls == 0


# ---- 9: invalid uploads --------------------------------------------------------------------------
def test_corrupt_unsupported_empty_and_missing(make_det_client):
    c, det, _ = make_det_client()
    r = dpost(c, make_image()[:60])
    assert r.status_code == 400 and r.json()["error"]["code"] == "CORRUPT_IMAGE"
    r = dpost(c, b"not an image at all", "x.png", "image/png")
    assert r.status_code == 415 and r.json()["error"]["code"] == "UNSUPPORTED_FORMAT"
    assert dpost(c, make_image("GIF"), "a.gif", "image/png").status_code == 415  # lying MIME, real GIF
    assert dpost(c, make_image(), "a.txt", "text/plain").status_code == 415
    r = dpost(c, b"")
    assert r.status_code == 400 and r.json()["error"]["code"] == "EMPTY_FILE"
    r = c.post(URL, data={"x": "y"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "MISSING_FILE"
    for resp in (r,):
        DetectionResponse.model_validate(resp.json())  # error bodies use the detection contract
    assert det.load_calls == 0  # nothing invalid ever reached the model


def test_limits_reuse_the_upload_policy(make_det_client):
    c, det, _ = make_det_client(max_upload_bytes=1000)
    r = dpost(c, b"0" * 200_000)  # rejected from Content-Length before parsing
    assert r.status_code == 413 and r.json()["error"]["details"]["limit_bytes"] == 1000
    DetectionResponse.model_validate(r.json())
    c, det, _ = make_det_client(max_image_pixels=1000)
    assert dpost(c, make_image(size=(100, 100))).json()["error"]["code"] == "IMAGE_DIMENSIONS_EXCEEDED"
    c, det, _ = make_det_client(max_image_side=50)
    assert dpost(c, make_image(size=(100, 10))).status_code == 413
    assert det.load_calls == 0


def test_chunked_upload_without_content_length_rejected(make_det_client):
    c, _, _ = make_det_client()
    r = c.post(URL, content=iter([b"abc"]), headers={"Content-Type": "multipart/form-data; boundary=x"})
    assert r.status_code == 411 and r.json()["error"]["code"] == "LENGTH_REQUIRED"
    DetectionResponse.model_validate(r.json())


# ---- 8/11: backend unavailable and failures --------------------------------------------------------
def test_backend_unavailable_is_honest(make_det_client):
    c, _, _ = make_det_client(FakeDetector(available=False))
    r = dpost(c, make_image())
    body = r.json()
    assert r.status_code == 503 and body["status"] == "unavailable" and body["detections"] == []
    assert body["error"]["code"] == "DETECTOR_UNAVAILABLE"


def test_disabled_by_configuration(make_det_client):
    c, det, _ = make_det_client(detection_enabled=False)
    r = dpost(c, make_image())
    assert r.status_code == 503 and r.json()["error"]["code"] == "DETECTION_DISABLED" and det.load_calls == 0


def test_load_failure_hides_internal_text_and_flips_capability(make_det_client):
    c, _, _ = make_det_client(FakeDetector(load_error="C:\\secret\\path\\yolox.onnx corrupt"))
    r = dpost(c, make_image())
    assert r.status_code == 503 and r.json()["error"]["code"] == "DETECTOR_LOAD_FAILED" and "secret" not in r.text
    cap = c.get("/api/v1/detection/capabilities").json()["detection"]
    assert cap["status"] == "unavailable" and "secret" not in str(cap)  # not "available" after a failed load


def test_runtime_failure_hides_internal_text(make_det_client):
    c, _, _ = make_det_client(FakeDetector(run_error="boom /etc/passwd"))
    r = dpost(c, make_image())
    assert r.status_code == 500 and r.json()["error"]["code"] == "DETECTOR_FAILED" and "passwd" not in r.text
    DetectionResponse.model_validate(r.json())


def test_first_response_reports_model_hash_known_only_after_load(make_det_client):
    c, det, _ = make_det_client()
    assert c.get("/api/v1/detection/capabilities").json()["detection"]["model"]["sha256"] is None
    body = dpost(c, make_image()).json()
    assert body["model"]["sha256"] == "f" * 64  # not null on the very first request


def test_model_loaded_once(make_det_client):
    c, det, _ = make_det_client()
    dpost(c, make_image())
    dpost(c, make_image())
    assert det.load_calls == 1


def test_unhandled_error_uses_detection_shape(make_det_client, monkeypatch):
    c, _, _ = make_det_client()

    async def boom(*a, **k):
        raise KeyError("secret")

    monkeypatch.setattr(c.app.state.detection_service, "process", boom)
    r = dpost(c, make_image())
    assert r.status_code == 500 and r.json()["error"]["code"] == "INTERNAL_ERROR" and "secret" not in r.text
    DetectionResponse.model_validate(r.json())


def test_filename_sanitized(make_det_client):
    c, _, _ = make_det_client()
    assert dpost(c, make_image(), "..\\..\\evil/../pic.png").json()["filename"] == "pic.png"


# ---- 12: capabilities ---------------------------------------------------------------------------------
def test_capabilities_distinguish_implemented_available_unavailable_not_implemented(make_det_client):
    c, _, _ = make_det_client()
    caps = c.get("/api/v1/capabilities").json()
    assert caps["detection"]["implemented"] is True and caps["detection"]["status"] == "available"
    assert caps["detection"]["model_loaded"] is False  # available is not the same as loaded
    assert caps["ocr"]["implemented"] is True and caps["ocr"]["status"] == "available"
    assert caps["spatial"] == {"implemented": False, "status": "not_implemented"}
    assert caps["models"]["max_resident"] == 1 and set(caps["models"]["state"]) == {"ocr", "detection"}
    dpost(c, make_image())
    assert c.get("/api/v1/detection/capabilities").json()["detection"]["model_loaded"] is True


def test_capabilities_unavailable_and_disabled(make_det_client):
    c, _, _ = make_det_client(FakeDetector(available=False))
    cap = c.get("/api/v1/detection/capabilities").json()["detection"]
    assert cap["implemented"] is True and cap["status"] == "unavailable" and "not installed" in cap["reason"]
    assert c.get("/health").json()["capabilities"]["detection"]["status"] == "unavailable"
    c, _, _ = make_det_client(detection_enabled=False)
    assert c.get("/api/v1/detection/capabilities").json()["detection"]["status"] == "disabled"


def test_real_default_backend_reports_unavailable_without_model(tmp_path):
    """No model file and no fake: the capability must say so (never 'available' because a route exists)."""
    s = dataclasses.replace(Settings(), detection_model_path=str(tmp_path / "missing.onnx"))
    c = TestClient(create_app(s, FakeOCR()), raise_server_exceptions=False)
    cap = c.get("/api/v1/detection/capabilities").json()["detection"]
    assert cap["status"] == "unavailable" and "missing.onnx" in cap["reason"] and str(tmp_path) not in cap["reason"]
    r = dpost(c, make_image())
    assert r.status_code == 503 and r.json()["error"]["code"] == "DETECTOR_UNAVAILABLE"


# ---- 14: OCR regression -----------------------------------------------------------------------------------
def test_ocr_endpoint_and_capabilities_unchanged_by_detection(make_det_client):
    c, _, ocr = make_det_client(FakeDetector(available=False))  # even with detection down
    r = post(c, make_image())
    assert r.status_code == 200 and r.json()["detected_text"] == "Hello World\nSecond line"
    assert r.json()["schema_version"] == "0.2-ocr-mvp" and ocr.load_calls == 1
    body = c.get("/api/v1/ocr/capabilities").json()
    assert body["limits"]["max_upload_bytes"] == 10_485_760 and body["queue"]["capacity"] == 5
    assert "detection" not in body  # legacy shape preserved
    assert c.get("/health").json()["capabilities"]["ocr"]["status"] == "available"


def test_ocr_errors_keep_the_ocr_shape(make_det_client):
    c, _, _ = make_det_client()
    r = c.post("/api/v1/ocr", data={"x": "y"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "MISSING_FILE" and "detected_text" in r.json()


# ---- 7: orchestration ----------------------------------------------------------------------------------------
def test_service_backpressure_and_slot_release():
    gate = threading.Event()
    svc = DetectionService(FakeDetector(gate=gate), dataclasses.replace(Settings(), worker_concurrency=1,
                                                                        queue_max_size=0))

    async def scenario():
        first = asyncio.create_task(svc.process(make_image(), "a", "image/png", "r1"))
        await asyncio.sleep(0.2)
        second = await svc.process(make_image(), "b", "image/png", "r2")
        gate.set()
        return second, await first

    second, first = asyncio.run(scenario())
    assert second.error.code == "QUEUE_FULL" and first.status == "succeeded" and svc.inflight == 0


def test_service_timeout_then_slot_released():
    svc = DetectionService(FakeDetector(delay=0.5), Settings())
    svc.settings = dataclasses.replace(svc.settings, task_timeout_seconds=0.1)
    resp = asyncio.run(svc.process(make_image(), "a", "image/png", "r1"))
    assert resp.error.code == "TASK_TIMEOUT" and resp.status == "failed"
    deadline = time.time() + 3
    while svc.inflight and time.time() < deadline:
        time.sleep(0.05)
    assert svc.inflight == 0


def test_service_shutdown_rejects_new_work():
    svc = DetectionService(FakeDetector(), Settings())
    svc.shutdown()
    resp = asyncio.run(svc.process(make_image(), "a", "image/png", "r"))
    assert resp.error.code == "SERVER_SHUTTING_DOWN" and svc.inflight == 0


def test_lifespan_shutdown_closes_both_services():
    app = create_app(Settings(), FakeOCR(), FakeDetector())
    with TestClient(app) as c:
        assert c.get("/health").status_code == 200
    assert app.state.service._closed and app.state.detection_service._closed


# ---- 15/16: shared lifecycle and concurrency -----------------------------------------------------------------------
def test_one_model_resident_by_default_and_unload_happens_between_requests(make_det_client):
    c, det, ocr = make_det_client()
    assert post(c, make_image()).status_code == 200
    assert ocr._loaded and not det._loaded
    assert dpost(c, make_image()).status_code == 200
    assert det._loaded and not ocr._loaded and ocr.unload_calls == 1  # OCR was evicted to make room
    assert post(c, make_image()).status_code == 200
    assert ocr._loaded and not det._loaded and det.unload_calls == 1
    assert ocr.load_calls == 2  # evicted models reload on demand


def test_two_resident_models_when_configured(make_det_client):
    c, det, ocr = make_det_client(max_resident_models=2)
    post(c, make_image())
    dpost(c, make_image())
    assert ocr._loaded and det._loaded and ocr.unload_calls == det.unload_calls == 0


def test_busy_model_is_never_unloaded_and_waiter_times_out():
    gate = threading.Event()
    ocr, det = FakeOCR(gate=gate), FakeDetector()
    s = dataclasses.replace(Settings(), model_acquire_timeout_seconds=1, worker_concurrency=1)
    mgr = ModelManager(1, 0.5)
    ocr_svc, det_svc = OCRService(ocr, s, mgr), DetectionService(det, s, mgr)

    async def scenario():
        running = asyncio.create_task(ocr_svc.process(make_image(), "a", "image/png", "o1"))
        await asyncio.sleep(0.3)  # OCR is now inside recognize() holding its model
        blocked = await det_svc.process(make_image(), "b", "image/png", "d1")
        unloaded_while_busy = ocr.unload_calls
        gate.set()
        return blocked, unloaded_while_busy, await running

    blocked, unloaded_while_busy, running = asyncio.run(scenario())
    assert blocked.error.code == "MODEL_BUSY" and blocked.error.retryable and blocked.status == "failed"
    assert unloaded_while_busy == 0 and running.status == "succeeded" and not det._loaded


def test_waiter_proceeds_when_the_holder_finishes():
    gate = threading.Event()
    ocr, det = FakeOCR(gate=gate), FakeDetector()
    s = Settings()
    mgr = ModelManager(1, 5.0)
    ocr_svc, det_svc = OCRService(ocr, s, mgr), DetectionService(det, s, mgr)

    async def scenario():
        running = asyncio.create_task(ocr_svc.process(make_image(), "a", "image/png", "o1"))
        await asyncio.sleep(0.3)
        waiting = asyncio.create_task(det_svc.process(make_image(), "b", "image/png", "d1"))
        await asyncio.sleep(0.3)
        gate.set()
        return await running, await waiting

    ocr_resp, det_resp = asyncio.run(scenario())
    assert ocr_resp.status == "succeeded" and det_resp.status == "succeeded"
    assert ocr.unload_calls == 1 and det._loaded and not ocr._loaded


def test_unload_failure_is_reported_not_ignored():
    ocr, det = FakeOCR(), FakeDetector()
    ocr.unload = lambda: (_ for _ in ()).throw(RuntimeError("stuck"))
    s = Settings()
    mgr = ModelManager(1, 1.0)
    ocr_svc, det_svc = OCRService(ocr, s, mgr), DetectionService(det, s, mgr)
    asyncio.run(ocr_svc.process(make_image(), "a", "image/png", "o1"))
    resp = asyncio.run(det_svc.process(make_image(), "b", "image/png", "d1"))
    assert resp.error.code == "MODEL_UNLOAD_FAILED" and not det._loaded  # cap not silently exceeded


def test_concurrent_requests_initialize_the_model_once():
    det = FakeDetector(delay=0.05)
    s = dataclasses.replace(Settings(), worker_concurrency=4, queue_max_size=8)
    svc = DetectionService(det, s, ModelManager(1, 5.0))

    async def scenario():
        return await asyncio.gather(*[svc.process(make_image(), "a", "image/png", f"r{i}") for i in range(8)])

    results = asyncio.run(scenario())
    assert all(r.status == "succeeded" for r in results) and det.load_calls == 1 and svc.inflight == 0


def test_cancel_stops_a_waiter():
    gate = threading.Event()
    ocr = FakeOCR(gate=gate)
    mgr = ModelManager(1, 5.0)
    OCRService(ocr, Settings(), mgr)
    DetectionService(FakeDetector(), Settings(), mgr)
    holder_in = threading.Event()

    def hold():
        with mgr.use("ocr"):
            holder_in.set()
            gate.wait(5)

    t = threading.Thread(target=hold)
    t.start()
    assert holder_in.wait(2)
    cancel = threading.Event()
    threading.Timer(0.3, cancel.set).start()
    with pytest.raises(VistaError) as e:
        with mgr.use("detection", cancel):
            pass
    gate.set()
    t.join()
    assert e.value.code == "CANCELLED"


def test_manager_validation_and_close():
    with pytest.raises(ValueError):
        ModelManager(0)
    with pytest.raises(ValueError):
        ModelManager(1, 0)
    mgr = ModelManager(1, 1.0)
    mgr.register("m", load=lambda: None, is_loaded=lambda: True)
    with pytest.raises(ValueError):
        mgr.register("m", load=lambda: None, is_loaded=lambda: True)
    mgr.close()
    with pytest.raises(VistaError) as e:
        with mgr.use("m"):
            pass
    assert e.value.code == "SERVER_SHUTTING_DOWN"
    with pytest.raises(VistaError):
        ModelManager(1, 1.0).use("nope").__enter__()
