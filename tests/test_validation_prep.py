"""Audit tests added in the post-MVP validation stage. Mock-based unless stated."""
import asyncio
import dataclasses
import io
import json
import socket
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from apps.api.main import create_app
from core.config import Settings
from core.contracts import OCRResponse
from core.orchestration import OCRService
from core.vision.validation import ImageLimits, decode_image
from scripts.benchmark_ocr import load_fixtures, percentile, run_benchmark, similarity, stats
from tests.conftest import post
from tests.fakes import FakeOCR
from tests.netguard import block_network

FIX = Path(__file__).parent / "fixtures"


# ---- benchmark statistics (mock engine: tests the arithmetic and counting, not OCR) ----
def test_percentile_nearest_rank():
    v = list(range(1, 101))
    assert percentile(v, 95) == 95 and percentile(v, 50) == 50 and percentile([7], 95) == 7
    assert percentile([], 95) is None
    assert stats([10, 20, 30, 40])["median_ms"] == 25


def test_similarity_ignores_case_space_punct():
    assert similarity(["Hello VISTA"], "hello  vista!") == 1.0
    assert similarity([], "") == 1.0 and similarity([], "noise") == 0.0


def test_benchmark_counts_success_and_failure():
    fx = load_fixtures(FIX)
    fx.append({"file": "junk.png", "category": "bad", "width": 1, "height": 1, "expected_lines": [], "bytes": b"junk"})
    res = run_benchmark(FakeOCR(), fx, Settings(), runs=2, warmup=1)
    assert res["status"] == "completed"
    assert res["ok"] == 2 * len(MANIFEST_FILES) and res["failed"] == 2
    assert res["failures"][0]["code"] == "UNSUPPORTED_FORMAT"
    assert res["overall"]["n"] == res["ok"] and res["model_load_s"] >= 0


def test_benchmark_reports_unavailable_engine():
    res = run_benchmark(FakeOCR(available=False), load_fixtures(FIX), Settings())
    assert res["status"] == "engine_unavailable"


def test_benchmark_reports_load_failure():
    res = run_benchmark(FakeOCR(load_error="x"), load_fixtures(FIX), Settings())
    assert res["status"] == "engine_load_failed"


# ---- fixtures ----
MANIFEST = json.loads((FIX / "manifest.json").read_text(encoding="utf-8"))
MANIFEST_FILES = [m["file"] for m in MANIFEST]


def test_fixtures_are_valid_small_and_match_manifest():
    limits = ImageLimits(10_485_760, 6000, 20_000_000, frozenset({"PNG"}), frozenset({"image/png"}))
    total = 0
    for m in MANIFEST:
        data = (FIX / m["file"]).read_bytes()
        total += len(data)
        dec = decode_image(data, "image/png", limits)
        assert (dec.width, dec.height) == (m["width"], m["height"])
    assert total < 300_000 and any(not m["expected_lines"] for m in MANIFEST)


# ---- network guard self-test ----
def test_network_guard_blocks_external_but_not_loopback(monkeypatch):
    block_network(monkeypatch)
    with pytest.raises(RuntimeError):
        socket.create_connection(("8.8.8.8", 53), timeout=1)
    with pytest.raises(RuntimeError):
        socket.getaddrinfo("example.com", 80)
    socket.getaddrinfo("localhost", 80)  # allowed


# ---- decompression-bomb style inputs: rejected from the header, before full decode ----
def _bilevel_png(w, h):
    buf = io.BytesIO()
    Image.new("1", (w, h)).save(buf, "PNG")
    return buf.getvalue()


@pytest.mark.parametrize("w,h", [(7000, 7000), (12000, 12000), (20000, 20000)])
def test_huge_dimension_png_rejected(make_client, w, h, recwarn):
    c, eng = make_client()
    data = _bilevel_png(w, h)
    assert len(data) < 10_485_760
    r = post(c, data)
    assert r.status_code == 413 and r.json()["error"]["code"] == "IMAGE_DIMENSIONS_EXCEEDED"
    assert eng.load_calls == 0  # never reached the engine


# ---- shutdown / concurrency ----
def test_shutdown_rejects_new_work_and_cancels_queued():
    import threading

    gate = threading.Event()
    svc = OCRService(FakeOCR(gate=gate), dataclasses.replace(Settings(), worker_concurrency=1, queue_max_size=2))
    img = (FIX / "printed_en.png").read_bytes()

    async def scenario():
        running = asyncio.create_task(svc.process(img, "a", "image/png", "r1"))
        await asyncio.sleep(0.2)
        queued = asyncio.create_task(svc.process(img, "b", "image/png", "r2"))
        await asyncio.sleep(0.1)
        svc.shutdown()
        late = await svc.process(img, "c", "image/png", "r3")
        gate.set()
        return late, await running, await queued

    late, running, queued = asyncio.run(scenario())
    assert late.error.code == "SERVER_SHUTTING_DOWN"
    assert queued.error.code == "CANCELLED"  # queued task stopped before decoding
    assert running.status == "succeeded"  # a task already inside the engine finishes
    assert svc.inflight == 0


def test_app_lifespan_shutdown_closes_service():
    app = create_app(Settings(), FakeOCR())
    with TestClient(app) as c:
        assert c.get("/health").status_code == 200
        assert app.state.service._closed is False
    assert app.state.service._closed is True


def test_reserved_slot_not_leaked_when_executor_closed():
    svc = OCRService(FakeOCR(), Settings())
    svc._executor.shutdown(wait=False)  # simulate a closed executor without the closed flag
    resp = asyncio.run(svc.process((FIX / "printed_en.png").read_bytes(), "a", "image/png", "r"))
    assert resp.error.code == "SERVER_SHUTTING_DOWN" and svc.inflight == 0


def test_chunked_upload_without_content_length_rejected(make_client):
    c, _ = make_client()
    hdr = {"Content-Type": "multipart/form-data; boundary=x"}
    r = c.post("/api/v1/ocr", content=iter([b"abc", b"def"]), headers=hdr)
    assert r.status_code == 411 and r.json()["error"]["code"] == "LENGTH_REQUIRED"


# ---- contract characterization (documents drift from docs/DATA_CONTRACTS.md; see ADR-0004 proposal) ----
def test_response_shape_is_the_documented_mvp_shape():
    """Fails if the response shape changes silently. Changing it requires an ADR + this test update."""
    assert set(OCRResponse.model_fields) == {
        "schema_version", "request_id", "status", "filename", "image_width", "image_height", "coordinate_space",
        "detected_text", "blocks", "processing_time_ms", "engine", "warnings", "error", "raw"}
    assert OCRResponse(request_id="x", status="failed").schema_version == "0.2-ocr-mvp"


def test_dotenv_with_utf8_bom_is_read(tmp_path):
    from core.config import load_dotenv

    f = tmp_path / ".env"
    f.write_bytes("\ufeffVISTA_PORT=8123\n# comment\nVISTA_OCR_MAX_SIDE=900\n".encode("utf-8"))
    env: dict = {}
    load_dotenv(f, env)
    assert env == {"VISTA_PORT": "8123", "VISTA_OCR_MAX_SIDE": "900"}
    assert Settings.from_env(env).port == 8123
