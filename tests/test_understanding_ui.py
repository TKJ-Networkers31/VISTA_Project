"""Understanding page: static wiring only. Does not prove a browser, a key or the real provider works."""
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.api.main import create_app
from core.config import Settings
from tests.fakes import FakeDetector, FakeOCR
from tests.fakes_understanding import FakeUnderstanding

STATIC = Path(__file__).resolve().parents[1] / "apps" / "web" / "static"


@pytest.fixture
def client():
    return TestClient(create_app(Settings(), FakeOCR(), FakeDetector(), FakeUnderstanding()),
                      raise_server_exceptions=False)


def test_assets_are_served(client):
    for name in ("understanding.html", "understanding.js", "understanding.css"):
        assert client.get(f"/static/{name}").status_code == 200, name


def test_every_element_used_by_the_script_exists_in_the_page():
    html = (STATIC / "understanding.html").read_text(encoding="utf-8")
    js = (STATIC / "understanding.js").read_text(encoding="utf-8")
    for ident in set(re.findall(r'\$\("([\w-]+)"\)', js)):
        assert f'id="{ident}"' in html, ident


def test_script_uses_only_the_local_api_and_stores_nothing():
    js = (STATIC / "understanding.js").read_text(encoding="utf-8")
    for forbidden in ("WebSocket", "localStorage", "sessionStorage", "indexedDB", "eval(", "innerHTML", "api_key",
                      "Authorization"):
        assert forbidden not in js, forbidden
    assert "http://" not in js and "https://" not in js
    assert "/api/v1/understanding" in js and "/api/v1/understanding/capabilities" in js
    assert 'fd.append("consent_external", "true")' in js and "$(\"consent\").checked" in js


def test_page_discloses_that_the_feature_is_external_and_needs_consent():
    html = (STATIC / "understanding.html").read_text(encoding="utf-8")
    assert "not local" in html and "NVIDIA" in html and 'id="consent"' in html


def test_index_links_to_understanding_and_keeps_ocr_ids(client):
    html = client.get("/").text
    assert "/static/understanding.html" in html
    for ident in ("file-input", "run-btn", "clear-btn", "copy-btn", "text-out", "overlay", "blocks"):
        assert f'id="{ident}"' in html, ident
