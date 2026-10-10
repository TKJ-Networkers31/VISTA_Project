"""Local detection benchmark for the configured backend. Offline once the model file is installed.

Run:  python -m scripts.benchmark_detection [--runs 20] [--warmup 3] [--images DIR] [--out results] [--label "X270 AC"]

What it measures (provider level: letterbox + ONNX Runtime + decode/NMS; no HTTP, no image decoding):
  model init time, process RSS before/after load and before/after inference, peak RSS during inference,
  first (cold) inference, then warm latency per image size with median and p95, per-stage timings,
  detection count, versions, device. Failed runs are counted and listed, never hidden.

Input set (repeatable): deterministic synthetic images generated in memory from a fixed seed at 640x480, 1280x720,
1920x1080 and 3000x2000, or your own photos with --images DIR (jpg/png/webp). Synthetic images contain no real
objects, so their detection counts say nothing about accuracy; latency is comparable because the work per image is.

Limits: RSS is the WHOLE process (interpreter + libraries + model), not incremental model memory. Compare the
before/after-load difference only as a rough indication; the OS may keep freed memory. p95 over few samples ~ max.
Nothing here is a result until you ran it on the target machine; do not quote sandbox numbers as X270 numbers.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import platform
import sys
import time
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

from core.config import Settings
from scripts.benchmark_ocr import PeakSampler, rss_mb, stats

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ["onnxruntime", "numpy", "Pillow", "psutil", "fastapi", "pydantic", "rapidocr-onnxruntime"]
SYNTHETIC_SIZES = [(640, 480), (1280, 720), (1920, 1080), (3000, 2000)]
SEED = 20261009


def synthetic_image(size: Tuple[int, int], seed: int = SEED) -> Image.Image:
    """Deterministic RGB test image: smooth gradient + seeded rectangles + mild noise. Same bytes on every run."""
    import numpy as np

    w, h = size
    rng = np.random.default_rng(seed + w * 31 + h)
    x = np.linspace(0, 255, w, dtype=np.float32)[None, :, None]
    y = np.linspace(0, 255, h, dtype=np.float32)[:, None, None]
    img = np.concatenate([np.broadcast_to(x, (h, w, 1)), np.broadcast_to(y, (h, w, 1)),
                          np.broadcast_to((x + y) / 2, (h, w, 1))], axis=2)
    for _ in range(12):
        x0, y0 = int(rng.integers(0, w - 20)), int(rng.integers(0, h - 20))
        x1, y1 = min(w, x0 + int(rng.integers(20, w // 3))), min(h, y0 + int(rng.integers(20, h // 3)))
        img[y0:y1, x0:x1] = rng.integers(0, 255, 3)
    img = np.clip(img + rng.normal(0, 4, img.shape), 0, 255).astype(np.uint8)
    return Image.fromarray(img, "RGB")


def load_inputs(directory: Optional[Path]) -> List[Tuple[str, Image.Image]]:
    if directory is None:
        return [(f"synthetic_{w}x{h}", synthetic_image((w, h))) for w, h in SYNTHETIC_SIZES]
    files = sorted(p for p in directory.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})
    return [(p.name, Image.open(p).convert("RGB")) for p in files]


def machine_info() -> Dict[str, Any]:
    try:
        import psutil
    except ImportError:
        psutil = None
    packages = {}
    for name in PACKAGES:
        try:
            packages[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            packages[name] = None
    providers: Any
    try:
        import onnxruntime as ort

        providers = ort.get_available_providers()
    except Exception as exc:
        providers = f"onnxruntime import failed: {type(exc).__name__}"
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python": sys.version.split()[0], "python_impl": platform.python_implementation(),
        "platform": platform.platform(), "machine": platform.machine(), "processor": platform.processor(),
        "cpu_count_logical": psutil.cpu_count() if psutil else None,
        "total_ram_mb": round(psutil.virtual_memory().total / 1048576) if psutil else None,
        "available_ram_mb_at_start": round(psutil.virtual_memory().available / 1048576) if psutil else None,
        "packages": packages, "onnxruntime_providers": providers,
    }


def run_benchmark(provider, inputs: List[Tuple[str, Image.Image]], settings: Settings, runs: int = 20,
                  warmup: int = 3) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "backend": settings.detection_backend, "engine": provider.info().model_dump(),
        "model": provider.model_info().model_dump(), "device": "cpu (CPUExecutionProvider)",
        "runs_per_image": runs, "warmup_calls": warmup, "conf_threshold": settings.detection_conf_threshold,
        "nms_iou": settings.detection_nms_iou, "max_detections": settings.detection_max_detections,
        "input_size": settings.detection_input_size, "threads_setting": settings.detection_threads,
        "images": [{"name": n, "width": im.width, "height": im.height} for n, im in inputs],
    }
    ok, reason = provider.is_available()
    if not ok:
        result.update(status="backend_unavailable", reason=reason)
        return result
    result["rss_mb_before_load"] = rss_mb()
    t0 = time.perf_counter()
    try:
        provider.load()
    except Exception as exc:
        result.update(status="backend_load_failed", reason=type(exc).__name__)
        return result
    result["model_load_s"] = round(time.perf_counter() - t0, 3)
    result["model"] = provider.model_info().model_dump()  # now carries the file's SHA-256
    result["rss_mb_after_load"] = rss_mb()

    failures: List[Dict[str, str]] = []
    per_image: Dict[str, Dict[str, Any]] = {n: {"ms": [], "stages": {"preprocess_ms": [], "inference_ms": [],
                                                                      "postprocess_ms": []}, "n_det": None}
                                            for n, _ in inputs}

    def one(name: str, img: Image.Image, record: bool) -> Optional[float]:
        t = time.perf_counter()
        try:
            raw = provider.detect(img, settings.detection_conf_threshold, settings.detection_nms_iou,
                                  settings.detection_max_detections)
        except Exception as exc:
            if record:
                failures.append({"image": name, "error": type(exc).__name__})
            return None
        ms = (time.perf_counter() - t) * 1000
        if record:
            rec = per_image[name]
            rec["ms"].append(ms)
            rec["n_det"] = len(raw.detections)
            for k, v in getattr(provider, "last_timings", {}).items():
                rec["stages"].setdefault(k, []).append(v)
        return ms

    result["rss_mb_before_inference"] = rss_mb()
    with PeakSampler() as sampler:
        first_name, first_img = inputs[0]
        first = one(first_name, first_img, record=False)
        result["first_inference_ms"] = None if first is None else round(first, 1)
        result["rss_mb_after_first_inference"] = rss_mb()
        for i in range(warmup):
            one(*inputs[i % len(inputs)], record=False)
        for _ in range(runs):
            for name, img in inputs:
                one(name, img, record=True)
    result["rss_mb_peak_during_inference"] = sampler.peak
    result["rss_mb_after_inference"] = rss_mb()

    all_ms = [m for d in per_image.values() for m in d["ms"]]
    result["overall"] = stats(all_ms)
    result["per_image"] = {}
    for name, img in inputs:
        d = per_image[name]
        stage_medians = {k: (round(sorted(v)[len(v) // 2], 2) if v else None) for k, v in d["stages"].items()}
        result["per_image"][name] = {"width": img.width, "height": img.height, "detections": d["n_det"],
                                     "stage_median_ms": stage_medians, **stats(d["ms"])}
    result["ok_runs"], result["failed_runs"], result["failures"] = len(all_ms), len(failures), failures
    result["status"] = "completed" if all_ms else "no_successful_runs"
    return result


def summary_lines(report: Dict[str, Any]) -> List[str]:
    b, m = report["benchmark"], report["machine"]
    lines = [f"python {m['python']} | {m['platform']} | cpus={m['cpu_count_logical']} ram_mb={m['total_ram_mb']}",
             f"backend={b['backend']} model={b['model'].get('id')} sha256={str(b['model'].get('sha256'))[:16]}... "
             f"input={b['input_size']} threads={b['threads_setting']} device={b['device']}",
             f"status: {b['status']}" + (f" ({b.get('reason')})" if b.get("reason") else "")]
    if b["status"] in ("completed", "no_successful_runs"):
        o = b["overall"]
        lines += [f"model load: {b['model_load_s']} s | first inference: {b['first_inference_ms']} ms",
                  f"warm: n={o['n']} median={o['median_ms']} ms p95={o['p95_ms']} ms (p95 over few samples ~ max)"]
        for name, d in b["per_image"].items():
            lines.append(f"  {name:22s} {d['width']}x{d['height']:<5} median={d['median_ms']} ms p95={d['p95_ms']} ms "
                         f"detections={d['detections']} stages(ms)={d['stage_median_ms']}")
        lines += [f"RSS MB (whole process): before load={b['rss_mb_before_load']} after load={b['rss_mb_after_load']} "
                  f"before inference={b['rss_mb_before_inference']} after 1st inference="
                  f"{b['rss_mb_after_first_inference']} peak during={b['rss_mb_peak_during_inference']} "
                  f"after={b['rss_mb_after_inference']} (None = psutil not installed)",
                  f"ok={b['ok_runs']} failed={b['failed_runs']} {b['failures']}"]
    return lines


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--runs", type=int, default=20, help="timed repetitions per image after warm-up")
    ap.add_argument("--warmup", type=int, default=3, help="discarded calls after the first (cold) call")
    ap.add_argument("--images", type=Path, default=None, help="directory of your own images instead of synthetic")
    ap.add_argument("--out", type=Path, default=ROOT / "results")
    ap.add_argument("--label", default="", help="free text, e.g. 'X270 on AC power, browser closed'")
    args = ap.parse_args(argv)
    if args.runs < 1 or args.warmup < 0:
        ap.error("--runs must be >= 1 and --warmup >= 0")

    from core.config import load_dotenv
    from core.detection import create_detection_provider

    load_dotenv(ROOT / ".env")
    settings = Settings.from_env()
    inputs = load_inputs(args.images)
    if not inputs:
        ap.error("no images found in --images")
    provider = create_detection_provider(settings)
    report = {"label": args.label, "machine": machine_info(),
              "settings": {k: v for k, v in dataclasses.asdict(settings).items() if k.startswith("detection_")},
              "benchmark": run_benchmark(provider, inputs, settings, args.runs, args.warmup)}
    args.out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = args.out / f"benchmark-detection-{platform.system().lower()}-py{platform.python_version()}-{stamp}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("\n".join(summary_lines(report)))
    print(f"report: {path}")
    status = report["benchmark"]["status"]
    if status != "completed":
        return 2
    return 0 if report["benchmark"]["failed_runs"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
