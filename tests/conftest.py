import dataclasses
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from apps.api.main import create_app
from core.config import Settings
from tests.fakes import FakeOCR


def make_image(fmt="PNG", size=(200, 100), color="white"):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, fmt)
    return buf.getvalue()


@pytest.fixture
def settings():
    return Settings()


@pytest.fixture
def make_client(settings):
    def _make(engine=None, **overrides):
        s = dataclasses.replace(settings, **overrides)
        engine = engine or FakeOCR()
        return TestClient(create_app(s, engine), raise_server_exceptions=False), engine

    return _make


def post(client, data, name="a.png", mime="image/png", **params):
    return client.post("/api/v1/ocr", files={"file": (name, data, mime)}, params=params)


@pytest.fixture(autouse=True)
def _offline_for_real_engine_tests(request, monkeypatch):
    """Real-engine tests must work with no internet: block non-loopback sockets while they run."""
    if request.node.get_closest_marker("requires_model"):
        from tests.netguard import block_network

        block_network(monkeypatch)
