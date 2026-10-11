"""REAL NVIDIA NIM call. Opt-in: excluded from the default run and skipped without a key.

Run (PowerShell):  $env:VISTA_NIM_API_KEY = "<your key>"; python -m pytest -m requires_network -s tests/test_nim_real.py
Uses a synthetic image generated here (no personal data). It sends ONE small request to the hosted NVIDIA API.
Passing proves: auth works, the request shape is accepted and the response has choices[0].message.content.
It does NOT prove answer quality, latency targets, quotas or that the free endpoint stays available.
"""
import io
import os
import time

import pytest
from PIL import Image, ImageDraw

from core.config import Settings
from core.providers.nim import NimAdapter, NimConfig

pytestmark = pytest.mark.requires_network


def _image() -> bytes:
    img = Image.new("RGB", (320, 240), (250, 250, 250))
    ImageDraw.Draw(img).rectangle([60, 60, 260, 180], fill=(200, 30, 30))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def test_real_nim_answers_about_a_synthetic_image():
    key = os.environ.get("VISTA_NIM_API_KEY", "")
    if not key:
        pytest.skip("set VISTA_NIM_API_KEY to run the real NVIDIA NIM test")
    s = Settings.from_env()
    adapter = NimAdapter(NimConfig(api_key=key, base_url=s.nim_base_url, model=s.nim_model,
                                   timeout_seconds=s.external_timeout_seconds, max_tokens=s.nim_max_tokens,
                                   enable_thinking=s.nim_enable_thinking, max_retries=s.external_retry_max))
    t0 = time.perf_counter()
    answer = adapter.ask(_image(), "What color is the large shape? Answer in one short sentence.")
    ms = round((time.perf_counter() - t0) * 1000)
    print(f"\nmodel={s.nim_model} ms={ms} answer={answer!r}")
    assert isinstance(answer, str) and answer.strip()
