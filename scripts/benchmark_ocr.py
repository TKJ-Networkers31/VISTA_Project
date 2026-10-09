"""Local OCR benchmark. Offline: needs no internet, API key or extra downloads once dependencies are installed.

Run:  python -m scripts.benchmark_ocr [--runs 5] [--warmup 2] [--fixtures tests/fixtures] [--out results]

Measures end-to-end service latency (validate + decode + downscale + OCR + normalize) on synthetic fixtures.
"Similarity" is a rough text-overlap ratio against the fixture's known text; it is NOT an accuracy benchmark.
Nothing here is a result until it has actually been run on the target machine.
"""
from __future__ import annotations

import argparse
import asyncio
import dataclasses
import difflib
import json
import math
import platform
import re
import socket
import statistics
import sys
import threading
import time
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.config import Settings
from core.orchestration import OCRService

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ["rapidocr-onnxruntime", "onnxruntime", "numpy", "opencv-python", "Pillow", "pyclipper", "Shapely",
            "fastapi", "starlette", "uvicorn", "pydantic", "psutil"]


# ---------- helpers ----------
def percentile(values: List[float], p: float) -> Optional[float]:
    """Nearest-rank percentile. With few samples p95 is effectively the max; check `n`."""
    if not values:
        return None
    s = sorted(values)
    return s[max(1, math.ceil(p / 100 * len(s))) - 1]


def stats(values: List[float]) -> Dict[str, Any]:
    if not values:
        return {"n": 0, "median_ms": None, "p95_ms": None, "min_ms": None, "max_ms": None}
    return {"n": len(values), "median_ms": round(statistics.median(values), 1),
            "p95_ms": round(percentile(values, 95), 1), "min_ms": round(min(values), 1),
            "max_ms": round(max(values), 1)}


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def similarity(expected_lines: List[str], detected: str) -> float:
    exp, got = norm("".join(expected_lines)), norm(detected)
    if not exp and not got:
        return 1.0
    return round(difflib.SequenceMatcher(None, exp, got).ratio(), 3)


def _psutil():
    try:
        import psutil
        return psutil
    except ImportError:
        return None


def rss_mb() -> Optional[float]:
    ps = _psutil()
    if ps is None:
        return None
    return round(ps.Process().memory_info().rss / 1048576, 1)


class PeakSampler:
    """Samples process RSS in a background thread; reports the max seen (None if psutil is missing)."""

    def __init__(self, interval: float = 0.05) -> None:
        self.interval, self.peak, self._stop = interval, None, threading.Event()
        self._t = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self._stop.is_set():
            v = rss_mb()
            if v is not None and (self.peak is None or v > self.peak):
                self.peak = v
            self._stop.wait(self.interval)

    def __enter__(self):
        self._t.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._t.join(1)


def machine_info() -> Dict[str, Any]:
    ps = _psutil()
    pk = {}
    for name in PACKAGES:
        try:
            pk[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            pk[name] = None
    providers = None
    try:
        import onnxruntime as ort
        providers = ort.get_available_providers()
    except Exception as exc:  # report, do not hide, an import problem
        providers = f"onnxruntime import failed: {type(exc).__name__}"
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hostname_hash": hex(abs(hash(socket.gethostname())) % 0xFFFFFF),  # not the real hostname
        "python": sys.version.split()[0], "python_impl": platform.python_implementation(),
        "platform": platform.platform(), "machine": platform.machine(), "processor": platform.processor(),
        "cpu_count_logical": ps.cpu_count() if ps else None,
        "total_ram_mb": round(ps.virtual_memory().total / 1048576) if ps else None,
        "available_ram_mb_at_start": round(ps.virtual_memory().available / 1048576) if ps else None,
        "packages": pk, "onnxruntime_providers": providers,
    }


# ---------- benchmark ----------
def load_fixtures(directory: Path) -> List[Dict[str, Any]]:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    for m in manifest:
        m["bytes"] = (directory / m["file"]).read_bytes()
    return manifest


def run_benchmark(provider, fixtures: List[Dict[str, Any]], settings: Settings, runs: int = 5,
                  warmup: int = 2) -> Dict[str, Any]:
    svc = OCRService(provider, settings)
    result: Dict[str, Any] = {"engine": provider.info().model_dump(), "runs": runs, "warmup_calls": warmup,
                              "ocr_max_side": settings.ocr_max_side}
    ok_avail, reason = provider.is_available()
    if not ok_avail:
        result.update(status="engine_unavailable", reason=reason)
        return result

    result["rss_mb_before_load"] = rss_mb()
    t0 = time.perf_counter()
    try:
        provider.load()
    except Exception as exc:
        result.update(status="engine_load_failed", reason=type(exc).__name__)
        return result
    result["model_load_s"] = round(time.perf_counter() - t0, 2)
    result["rss_mb_after_load"] = rss_mb()

    async def go() -> None:
        counter = {"ok": 0, "failed": 0}
        failures: List[Dict[str, str]] = []
        per_image: Dict[str, Dict[str, Any]] = {f["file"]: {"category": f["category"], "ms": [], "similarity": None,
                                                               "pixels": f["width"] * f["height"]} for f in fixtures}

        async def one(fx: Dict[str, Any], record: bool):
            t = time.perf_counter()
            resp = await svc.process(fx["bytes"], fx["file"], "image/png", "bench")
            ms = (time.perf_counter() - t) * 1000
            if resp.status == "succeeded":
                counter["ok"] += int(record)
                if record:
                    per_image[fx["file"]]["ms"].append(ms)
                    per_image[fx["file"]]["similarity"] = similarity(fx["expected_lines"], resp.detected_text)
            elif record:
                counter["failed"] += 1
                failures.append({"file": fx["file"], "code": resp.error.code if resp.error else "?"})
            return ms, resp.status

        with PeakSampler() as sampler:
            first_ms, first_status = await one(fixtures[0], record=False)  # cold: first OCR after model load
            result["first_ocr_ms"], result["first_ocr_status"] = round(first_ms, 1), first_status
            warm = []
            for i in range(warmup):
                ms, _ = await one(fixtures[i % len(fixtures)], record=False)
                warm.append(round(ms, 1))
            result["warmup_ms"] = warm
            for _ in range(runs):
                for fx in fixtures:
                    await one(fx, record=True)
        result["rss_mb_peak_during_ocr"] = sampler.peak
        result["rss_mb_after"] = rss_mb()
        all_ms = [m for d in per_image.values() for m in d["ms"]]
        result["overall"] = stats(all_ms)
        cats: Dict[str, List[float]] = {}
        for d in per_image.values():
            cats.setdefault(d["category"], []).extend(d["ms"])
        result["by_category"] = {k: stats(v) for k, v in cats.items()}
        result["per_image"] = {k: {"category": d["category"], "pixels": d["pixels"], **stats(d["ms"]),
                                   "similarity": d["similarity"]} for k, d in per_image.items()}
        result["ok"], result["failed"], result["failures"] = counter["ok"], counter["failed"], failures

    asyncio.run(go())
    svc.shutdown()
    result["status"] = "completed"
    return result


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--runs", type=int, default=5, help="repetitions over all fixtures after warm-up")
    ap.add_argument("--warmup", type=int, default=2, help="discarded calls after the first (cold) call")
    ap.add_argument("--fixtures", type=Path, default=ROOT / "tests" / "fixtures")
    ap.add_argument("--out", type=Path, default=ROOT / "results", help="directory for the JSON report")
    ap.add_argument("--label", default="", help="free text, e.g. 'X270 on battery'")
    args = ap.parse_args(argv)

    from core.config import load_dotenv
    from core.ocr import create_provider

    load_dotenv(ROOT / ".env")
    settings = Settings.from_env()
    fixtures = load_fixtures(args.fixtures)
    provider = create_provider(settings.ocr_engine)
    report = {"label": args.label, "machine": machine_info(), "settings": dataclasses.asdict(settings),
              "benchmark": run_benchmark(provider, fixtures, settings, args.runs, args.warmup)}
    args.out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = args.out / f"benchmark-{platform.system().lower()}-py{platform.python_version()}-{stamp}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    b = report["benchmark"]
    print(f"python {report['machine']['python']} | {report['machine']['platform']}")
    print(f"status: {b['status']}" + (f" ({b.get('reason')})" if b.get("reason") else ""))
    if b["status"] == "completed":
        print(f"model load: {b['model_load_s']} s | first OCR: {b['first_ocr_ms']} ms | warm-up: {b['warmup_ms']}")
        o = b["overall"]
        print(f"after warm-up: n={o['n']} median={o['median_ms']} ms p95={o['p95_ms']} ms (p95 over few samples ~ max)")
        for name, d in b["per_image"].items():
            print(f"  {name:22s} {d['pixels']:>8d}px median={d['median_ms']:>8} ms similarity={d['similarity']}")
        print(f"RSS MB: before load={b['rss_mb_before_load']} after load={b['rss_mb_after_load']} "
              f"peak during OCR={b['rss_mb_peak_during_ocr']} (None = psutil not installed)")
        print(f"ok={b['ok']} failed={b['failed']} {b['failures']}")
    print(f"report: {path}")
    return {"completed": 0 if report["benchmark"].get("failed", 0) == 0 else 1}.get(b["status"], 2)


if __name__ == "__main__":
    raise SystemExit(main())
