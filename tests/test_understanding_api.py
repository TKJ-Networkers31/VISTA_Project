"""Image understanding: API, routing modes, consent, error mapping, privacy. Fake provider only: no network, no key.

These tests prove the plumbing and the policy (nothing is sent unless allowed). They are NOT evidence that the real
NVIDIA endpoint answers: that is tests/test_nim_real.py (marker requires_network, needs VISTA_NIM_API_KEY).
"""
import asyncio
import dataclasses
import io
import json
import logging
import random

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from apps.api.main import create_app
from core.config import Settings
from core.contracts import UnderstandingResponse, VistaError
from core.orchestration import UnderstandingService
from core.providers.nim import NimAdapter, NimConfig
from tests.conftest import make_image, post
from tests.fakes import FakeDetector, FakeOCR
from tests.fakes_understanding import FakeUnderstanding

URL = "/api/v1/understanding"
KEY = "nvapi-SECRET-KEY-0123456789"


def make(adapter=None, **overrides):
    overrides.setdefault("external_enabled", True)
    s = dataclasses.replace(Settings(), **overrides)
    adapter = adapter or FakeUnderstanding()
    c = TestClient(create_app(s, FakeOCR(), FakeDetector(), adapter), raise_server_exceptions=False)
    return c, adapter


def ask(c, data=None, name="a.png", mime="image/png", **form):
    data = data if data is not None else make_image()
    return c.post(URL, files={"file": (name, data, mime)}, data=form)


# ---- routing modes -----------------------------------------------------------------------------
@pytest.mark.parametrize("consent", ["true", "false"])
def test_local_only_never_sends_anything(consent):
    c, a = make()
    r = ask(c, mode="local_only", consent_external=consent)
    body = r.json()
    assert r.status_code == 501 and body["error"]["code"] == "CAPABILITY_UNSUPPORTED"
    assert body["route"]["target"] == "none" and body["route"]["external_transmission"] is False
    assert a.calls == 0
    UnderstandingResponse.model_validate(body)


def test_default_mode_comes_from_configuration():
    c, a = make(policy_default="local_only")
    assert ask(c, consent_external="true").status_code == 501 and a.calls == 0
    c, a = make(policy_default="hybrid")
    assert ask(c, consent_external="true").status_code == 200 and a.calls == 1


def test_hybrid_without_consent_is_rejected_before_the_image_is_read():
    c, a = make()
    r = ask(c, make_image()[:60], mode="hybrid")  # even a corrupt image: policy comes first
    body = r.json()
    assert r.status_code == 403 and body["error"]["code"] == "CONSENT_REQUIRED" and a.calls == 0
    assert body["route"]["external_transmission"] is False


def test_hybrid_with_consent_succeeds_and_reports_the_route():
    c, a = make()
    r = ask(c, question="What animal?", mode="hybrid", consent_external="true")
    body = r.json()
    assert r.status_code == 200
    UnderstandingResponse.model_validate(body)
    assert body["status"] == "succeeded" and body["answer"] == "A cat on a sofa." and body["question"] == "What animal?"
    assert body["schema_version"] == "0.4-understanding" and (body["image_width"], body["image_height"]) == (200, 100)
    assert body["route"] == {"mode": "hybrid", "target": "external", "reason": "HYBRID_EXTERNAL",
                             "provider": "fake-nim", "model": "fake-vlm", "external_transmission": True}
    jpeg, question = a.seen
    assert jpeg[:2] == b"\xff\xd8" and question == "What animal?"  # a re-encoded JPEG, not the original PNG
    assert any("re-encoded" in w for w in body["warnings"])


def test_external_fallback_with_consent_uses_the_only_provider_and_without_consent_does_not():
    c, a = make()
    r = ask(c, mode="external_fallback", consent_external="true")
    assert r.status_code == 200 and r.json()["route"]["reason"] == "FALLBACK_NO_LOCAL" and a.calls == 1
    r = ask(c, mode="external_fallback")
    assert r.status_code == 403 and r.json()["error"]["code"] == "CONSENT_REQUIRED" and a.calls == 1


def test_master_switch_and_missing_credentials_block_every_send():
    c, a = make(external_enabled=False)
    r = ask(c, mode="hybrid", consent_external="true")
    assert r.status_code == 503 and r.json()["error"]["code"] == "EXTERNAL_DISABLED"
    assert r.json()["status"] == "unavailable" and a.calls == 0
    c, a = make(FakeUnderstanding(configured=False))
    r = ask(c, mode="hybrid", consent_external="true")
    assert r.status_code == 503 and r.json()["error"]["code"] == "EXTERNAL_NOT_CONFIGURED" and a.calls == 0


def test_invalid_mode_and_question():
    c, a = make()
    r = ask(c, mode="auto", consent_external="true")
    assert r.status_code == 400 and r.json()["error"]["code"] == "INVALID_MODE"
    for q in ("x" * 1001, "bad\x01char"):
        r = ask(c, question=q, mode="hybrid", consent_external="true")
        assert r.status_code == 400 and r.json()["error"]["code"] == "INVALID_PARAMETER"
    r = ask(c, mode="hybrid", consent_external="maybe")  # not a boolean
    assert r.status_code == 400 and r.json()["error"]["code"] == "INVALID_PARAMETER"
    UnderstandingResponse.model_validate(r.json())
    assert a.calls == 0


def test_blank_question_uses_the_default():
    c, a = make()
    body = ask(c, question="   ", mode="hybrid", consent_external="true").json()
    assert body["question"] == "Describe this image." and a.seen[1] == "Describe this image."


# ---- image validation (same limits as OCR/detection) ---------------------------------------------
def test_invalid_images_are_rejected_before_any_send():
    c, a = make()
    f = dict(mode="hybrid", consent_external="true")
    assert ask(c, make_image()[:60], **f).json()["error"]["code"] == "CORRUPT_IMAGE"
    assert ask(c, b"not an image", **f).status_code == 415
    assert ask(c, make_image("GIF"), "a.gif", "image/png", **f).status_code == 415
    assert ask(c, b"", **f).json()["error"]["code"] == "EMPTY_FILE"
    r = c.post(URL, data={"mode": "hybrid", "consent_external": "true"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "MISSING_FILE"
    UnderstandingResponse.model_validate(r.json())
    body = ask(c, make_image()[:60], **f).json()
    assert body["route"]["external_transmission"] is False
    assert a.calls == 0


def test_limits_reuse_the_upload_policy():
    c, a = make(max_upload_bytes=1000)
    r = ask(c, b"0" * 200_000, mode="hybrid", consent_external="true")
    assert r.status_code == 413 and r.json()["error"]["details"]["limit_bytes"] == 1000
    UnderstandingResponse.model_validate(r.json())
    c, a = make(max_image_pixels=1000)
    assert ask(c, mode="hybrid", consent_external="true").json()["error"]["code"] == "IMAGE_DIMENSIONS_EXCEEDED"
    assert a.calls == 0


def test_chunked_upload_without_content_length_rejected():
    c, _ = make()
    r = c.post(URL, content=iter([b"abc"]), headers={"Content-Type": "multipart/form-data; boundary=x"})
    assert r.status_code == 411 and r.json()["error"]["code"] == "LENGTH_REQUIRED"
    UnderstandingResponse.model_validate(r.json())


def test_large_image_is_downscaled_and_stays_under_the_size_cap():
    c, a = make(understanding_max_side=256, nim_max_image_bytes=50_000)
    big = io.BytesIO()
    Image.new("RGB", (2000, 1000), (10, 120, 200)).save(big, "PNG")
    assert ask(c, big.getvalue(), mode="hybrid", consent_external="true").status_code == 200
    sent = Image.open(io.BytesIO(a.seen[0]))
    assert max(sent.size) <= 256 and len(a.seen[0]) <= 50_000


def test_image_that_cannot_fit_the_provider_limit_is_rejected_unsent():
    c, a = make(nim_max_image_bytes=10_000, understanding_max_side=1024)
    noisy = Image.frombytes("RGB", (600, 600), random.Random(1).randbytes(600 * 600 * 3))
    buf = io.BytesIO()
    noisy.save(buf, "PNG")
    r = ask(c, buf.getvalue(), mode="hybrid", consent_external="true")
    assert r.status_code == 413 and r.json()["error"]["code"] == "IMAGE_TOO_LARGE_FOR_PROVIDER"
    assert a.calls == 0 and r.json()["route"]["external_transmission"] is False


# ---- provider failures map to distinguishable errors ---------------------------------------------
@pytest.mark.parametrize("category,code_,http,status", [
    ("timeout", "NIM_TIMEOUT", 504, "failed"), ("provider_internal", "NIM_AUTH_FAILED", 502, "failed"),
    ("resource_limit", "NIM_RATE_LIMITED", 429, "failed"), ("provider_internal", "NIM_MALFORMED", 502, "failed"),
    ("provider_internal", "NIM_SERVER_ERROR", 502, "failed"), ("unavailable", "NIM_NETWORK", 503, "unavailable"),
    ("resource_limit", "BUDGET_EXCEEDED", 429, "failed")])
def test_provider_errors(category, code_, http, status):
    c, a = make(FakeUnderstanding(error=VistaError(category, code_, "provider said no", True)))
    r = ask(c, mode="hybrid", consent_external="true")
    body = r.json()
    assert r.status_code == http and body["status"] == status and body["error"]["code"] == code_
    assert body["answer"] is None and body["route"]["external_transmission"] is True  # it was attempted
    UnderstandingResponse.model_validate(body)


def test_service_timeout_reports_that_the_request_was_sent():
    s = dataclasses.replace(Settings(), external_enabled=True, task_timeout_seconds=1)
    svc = UnderstandingService(FakeUnderstanding(delay=1.2), s)
    svc.settings = dataclasses.replace(svc.settings, task_timeout_seconds=0.5)
    resp = asyncio.run(svc.process(make_image(), "a.png", "image/png", "r", None, "hybrid", True))
    assert resp.error.code == "TASK_TIMEOUT" and resp.route.external_transmission is True


def test_service_shutdown_rejects_new_work():
    svc = UnderstandingService(FakeUnderstanding(), dataclasses.replace(Settings(), external_enabled=True))
    svc.shutdown()
    resp = asyncio.run(svc.process(make_image(), "a.png", "image/png", "r", None, "hybrid", True))
    assert resp.error.code == "SERVER_SHUTTING_DOWN" and resp.route.external_transmission is False


def test_backpressure_and_slot_release():
    s = dataclasses.replace(Settings(), external_enabled=True, worker_concurrency=1, queue_max_size=0)
    a = FakeUnderstanding(delay=0.4)
    svc = UnderstandingService(a, s)

    async def scenario():
        first = asyncio.create_task(svc.process(make_image(), "a", "image/png", "r1", None, "hybrid", True))
        await asyncio.sleep(0.15)
        second = await svc.process(make_image(), "b", "image/png", "r2", None, "hybrid", True)
        return second, await first

    second, first = asyncio.run(scenario())
    assert second.error.code == "QUEUE_FULL" and first.status == "succeeded"
    assert svc.inflight == 0 and a.calls == 1


# ---- secrets and logs ------------------------------------------------------------------------------
def test_key_question_and_image_never_reach_responses_or_logs(caplog):
    caplog.set_level(logging.DEBUG)
    calls = []

    def transport(url, headers, body, timeout):
        calls.append(headers)
        return 401, {}, KEY.encode()  # even a provider that echoes the key must not leak it

    adapter = NimAdapter(NimConfig(api_key=KEY, max_retries=0), transport=transport)
    c, _ = make(adapter, nim_api_key=KEY)
    r = ask(c, question="my private question 12345", mode="hybrid", consent_external="true")
    assert r.status_code == 502 and r.json()["error"]["code"] == "NIM_AUTH_FAILED" and len(calls) == 1
    assert KEY not in r.text and KEY not in caplog.text
    assert "my private question" not in caplog.text
    assert KEY not in c.get("/api/v1/understanding/capabilities").text
    assert KEY not in c.get("/api/v1/capabilities").text


def test_settings_repr_and_public_dict_hide_the_key():
    s = dataclasses.replace(Settings(), nim_api_key=KEY)
    assert KEY not in repr(s) and KEY not in json.dumps(s.public_dict()) and s.public_dict()["nim_api_key"] == "<set>"


# ---- capabilities ----------------------------------------------------------------------------------
def test_capabilities_states():
    c, _ = make()
    cap = c.get("/api/v1/understanding/capabilities").json()["understanding"]
    assert cap["status"] == "available" and cap["locality"] == "external" and cap["requires_consent"] is True
    assert cap["provides_bounding_boxes"] is False and cap["supports"] == ["image_understanding"]
    assert c.get("/api/v1/capabilities").json()["understanding"]["status"] == "available"
    c, _ = make(external_enabled=False)
    assert c.get("/api/v1/understanding/capabilities").json()["understanding"]["status"] == "disabled"
    c, _ = make(FakeUnderstanding(configured=False))
    assert c.get("/api/v1/understanding/capabilities").json()["understanding"]["status"] == "unavailable"


def test_real_default_adapter_without_key_is_unavailable_and_sends_nothing():
    s = dataclasses.replace(Settings(), external_enabled=True)  # real NimAdapter, no key
    c = TestClient(create_app(s, FakeOCR(), FakeDetector()), raise_server_exceptions=False)
    r = ask(c, mode="hybrid", consent_external="true")
    assert r.status_code == 503 and r.json()["error"]["code"] == "EXTERNAL_NOT_CONFIGURED"


# ---- regression: nothing else changed ---------------------------------------------------------------
def test_ocr_and_detection_unchanged_and_independent_of_understanding():
    c, a = make(external_enabled=False)
    r = post(c, make_image())
    assert r.status_code == 200 and r.json()["schema_version"] == "0.2-ocr-mvp"
    d = c.post("/api/v1/detection", files={"file": ("a.png", make_image(), "image/png")})
    assert d.status_code == 200 and d.json()["schema_version"] == "0.3-detection"
    assert a.calls == 0  # local capabilities never touch the external provider


def test_lifespan_shutdown_closes_the_service():
    c, _ = make()
    app = c.app
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
    assert app.state.understanding_service._closed is True
