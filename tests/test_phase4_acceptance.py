"""Phase 4 acceptance: routing safety proven with the REAL NimAdapter and a COUNTING transport. No network, no key.

Every test asserts how many HTTP requests reached the transport: for each rejected case that number must be 0.
These tests prove the policy and the error mapping; they do NOT prove that the real NVIDIA endpoint works.
"""
import dataclasses
import json
import logging

import pytest
from fastapi.testclient import TestClient

from apps.api.main import create_app
from core.config import Settings
from core.providers.nim import NimAdapter, NimConfig
from tests.conftest import make_image, post
from tests.fakes import FakeDetector, FakeOCR
from tests.netguard import block_network

URL = "/api/v1/understanding"
KEY = "nvapi-ACCEPTANCE-KEY-0123456789"
SECRET_QUESTION = "confidential question 8675309"


def ok_body(text="A red square."):
    return json.dumps({"choices": [{"message": {"content": text}}]}).encode()


class CountingTransport:
    def __init__(self, status=200, body=None, exc=None):
        self.status, self.body, self.exc = status, ok_body() if body is None else body, exc
        self.calls = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append(body)
        if self.exc is not None:
            raise self.exc
        return self.status, {}, self.body


def make(transport, key=KEY, **overrides):
    overrides.setdefault("external_enabled", True)
    overrides.setdefault("nim_api_key", key)
    s = dataclasses.replace(Settings(), **overrides)
    adapter = NimAdapter(NimConfig(api_key=key, max_retries=0), transport=transport)
    return TestClient(create_app(s, FakeOCR(), FakeDetector(), adapter), raise_server_exceptions=False)


def ask(c, **form):
    form.setdefault("question", SECRET_QUESTION)
    return c.post(URL, files={"file": ("a.png", make_image(), "image/png")}, data=form)


# ---- nothing is sent unless every condition holds ----------------------------------------------------
@pytest.mark.parametrize("consent", ["true", "false"])
def test_local_only_never_reaches_the_provider(consent):
    t = CountingTransport()
    r = ask(make(t), mode="local_only", consent_external=consent)
    assert r.status_code == 501 and r.json()["error"]["code"] == "CAPABILITY_UNSUPPORTED"
    assert t.calls == [] and r.json()["route"]["external_transmission"] is False


def test_default_mode_local_only_without_a_mode_never_reaches_the_provider():
    t = CountingTransport()
    r = ask(make(t, policy_default="local_only"), consent_external="true")
    assert r.status_code == 501 and t.calls == []


@pytest.mark.parametrize("mode", ["hybrid", "external_fallback"])
def test_external_modes_without_consent_never_reach_the_provider(mode):
    t = CountingTransport()
    r = ask(make(t), mode=mode)
    assert r.status_code == 403 and r.json()["error"]["code"] == "CONSENT_REQUIRED" and t.calls == []


def test_master_switch_off_and_missing_key_never_reach_the_provider():
    t = CountingTransport()
    r = ask(make(t, external_enabled=False), mode="hybrid", consent_external="true")
    assert r.status_code == 503 and r.json()["error"]["code"] == "EXTERNAL_DISABLED" and t.calls == []
    r = ask(make(t, key=""), mode="hybrid", consent_external="true")
    assert r.status_code == 503 and r.json()["error"]["code"] == "EXTERNAL_NOT_CONFIGURED" and t.calls == []


@pytest.mark.parametrize("mode", ["hybrid", "external_fallback"])
def test_external_modes_with_consent_send_exactly_one_request(mode):
    t = CountingTransport()
    r = ask(make(t), mode=mode, consent_external="true")
    body = r.json()
    assert r.status_code == 200 and body["answer"] == "A red square." and len(t.calls) == 1
    assert body["route"]["external_transmission"] is True
    sent = json.loads(t.calls[0])
    uri = sent["messages"][0]["content"][1]["image_url"]["url"]
    assert uri.startswith("data:image/jpeg;base64,") and sent["stream"] is False
    assert KEY.encode() not in t.calls[0]


def test_invalid_image_with_consent_is_rejected_before_any_request():
    t = CountingTransport()
    r = ask(make(t), mode="hybrid", consent_external="true")  # valid first, to prove the setup works
    assert r.status_code == 200 and len(t.calls) == 1
    r = make(t).post(URL, files={"file": ("a.png", make_image()[:60], "image/png")},
                     data={"mode": "hybrid", "consent_external": "true"})
    assert r.status_code == 400 and len(t.calls) == 1  # still 1: the corrupt image never reached the provider


# ---- provider errors, end to end through the real adapter ---------------------------------------------
@pytest.mark.parametrize("transport,http,code", [
    (CountingTransport(status=401), 502, "NIM_AUTH_FAILED"),
    (CountingTransport(status=403), 502, "NIM_AUTH_FAILED"),
    (CountingTransport(status=429), 429, "NIM_RATE_LIMITED"),
    (CountingTransport(status=500), 502, "NIM_SERVER_ERROR"),
    (CountingTransport(status=503), 502, "NIM_SERVER_ERROR"),
    (CountingTransport(exc=TimeoutError()), 504, "NIM_TIMEOUT"),
    (CountingTransport(exc=ConnectionResetError()), 503, "NIM_NETWORK"),
    (CountingTransport(body=b"not json"), 502, "NIM_MALFORMED"),
    (CountingTransport(body=b'{"choices": []}'), 502, "NIM_MALFORMED"),
    (CountingTransport(body=ok_body("   ")), 502, "NIM_EMPTY"),
])
def test_provider_errors_map_consistently_and_leak_nothing(transport, http, code):
    r = ask(make(transport), mode="hybrid", consent_external="true")
    body = r.json()
    assert r.status_code == http and body["error"]["code"] == code and body["answer"] is None
    assert body["route"]["external_transmission"] is True and len(transport.calls) == 1  # no retry configured
    assert KEY not in r.text and SECRET_QUESTION not in json.dumps(body["error"])


# ---- logs ----------------------------------------------------------------------------------------------
def test_key_question_answer_and_image_never_appear_in_logs(caplog):
    caplog.set_level(logging.DEBUG)
    t = CountingTransport(body=ok_body("secret answer 4242"))
    r = ask(make(t), mode="hybrid", consent_external="true")
    assert r.status_code == 200
    uri = json.loads(t.calls[0])["messages"][0]["content"][1]["image_url"]["url"]
    for forbidden in (KEY, SECRET_QUESTION, "secret answer 4242", uri[40:120]):
        assert forbidden not in caplog.text, forbidden[:12]


# ---- regression: local features never touch the external provider --------------------------------------
def test_ocr_and_detection_never_reach_the_external_provider():
    t = CountingTransport()
    c = make(t)
    assert post(c, make_image()).status_code == 200
    d = c.post("/api/v1/detection", files={"file": ("a.png", make_image(), "image/png")})
    assert d.status_code == 200 and t.calls == []
    assert post(c, make_image()).json()["schema_version"] == "0.2-ocr-mvp"
    assert d.json()["schema_version"] == "0.3-detection"


def test_local_only_with_the_real_default_transport_attempts_no_network(monkeypatch):
    block_network(monkeypatch)  # any real outbound connection or DNS lookup would raise
    s = dataclasses.replace(Settings(), external_enabled=True, nim_api_key=KEY)
    c = TestClient(create_app(s, FakeOCR(), FakeDetector()), raise_server_exceptions=False)  # real NimAdapter
    r = ask(c, mode="local_only", consent_external="true")
    assert r.status_code == 501 and r.json()["error"]["code"] == "CAPABILITY_UNSUPPORTED"
    r = ask(c, mode="hybrid")
    assert r.status_code == 403 and r.json()["error"]["code"] == "CONSENT_REQUIRED"
