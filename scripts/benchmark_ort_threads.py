"""Benchmark ONNX Runtime thread settings on a detection model. One child process per configuration (clean RSS).

Run:  python -m scripts.benchmark_ort_threads --model models\\yolox_nano.onnx --size 416
          [--configs 1:seq,2:seq,4:seq,2:par] [--runs 40] [--warmup 5] [--repeats 3] [--label "X270 AC"]

A config is `intra:mode` or `intra:mode:inter`; mode is seq|par. Measures raw `session.run` on a fixed random input
(inference only: no decoding, no pre/post-processing), so it isolates the thread effect. `--repeats` runs every
configuration several times, interleaved, and reports the per-repeat medians so run-to-run noise is visible.
Nothing here is a result until run on the target machine; close the browser/IDE and note the power mode in --label.
"""
from __future__ import annotations

import argparse
import json
import math
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
MODES = {"seq": "sequential", "par": "parallel"}


def parse_config(text: str) -> Tuple[int, str, int]:
    parts = text.strip().split(":")
    if len(parts) not in (2, 3) or parts[1] not in MODES:
        raise SystemExit(f"bad config {text!r}: use intra:seq|par[:inter]")
    try:
        intra = int(parts[0])
        inter = int(parts[2]) if len(parts) == 3 else 0
    except ValueError:
        raise SystemExit(f"bad config {text!r}: thread counts must be integers") from None
    if intra < 0 or inter < 0:
        raise SystemExit(f"bad config {text!r}: thread counts must be >= 0")
    return intra, MODES[parts[1]], inter


def percentile(values: List[float], p: float) -> Optional[float]:
    if not values:
        return None
    s = sorted(values)
    return s[max(1, math.ceil(p / 100 * len(s))) - 1]


def run_single(model: Path, size: int, cfg: Tuple[int, str, int], runs: int, warmup: int) -> Dict[str, Any]:
    import numpy as np
    import onnxruntime as ort

    from core.detection.ort_options import build_session_options

    try:
        import psutil

        proc = psutil.Process()
    except ImportError:
        proc = None
    options = build_session_options(ort, cfg[0], cfg[2], cfg[1])
    t0 = time.perf_counter()
    session = ort.InferenceSession(str(model), sess_options=options, providers=["CPUExecutionProvider"])
    load_s = time.perf_counter() - t0
    name = session.get_inputs()[0].name
    blob = np.random.default_rng(1).uniform(0, 255, (1, 3, size, size)).astype(np.float32)
    t = time.perf_counter()
    session.run(None, {name: blob})
    first_ms = (time.perf_counter() - t) * 1000
    for _ in range(warmup):
        session.run(None, {name: blob})
    times: List[float] = []
    peak = proc.memory_info().rss if proc else None
    for _ in range(runs):
        t = time.perf_counter()
        session.run(None, {name: blob})
        times.append((time.perf_counter() - t) * 1000)
        if proc:
            peak = max(peak, proc.memory_info().rss)
    return {"load_s": round(load_s, 3), "first_ms": round(first_ms, 1), "n": len(times),
            "median_ms": round(statistics.median(times), 1), "p95_ms": round(percentile(times, 95), 1),
            "max_ms": round(max(times), 1), "rss_peak_mb": None if peak is None else round(peak / 1048576, 1)}


def summarize(results: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
    summary: Dict[str, Dict[str, Any]] = {}
    for cfg, runs in results.items():
        good = [r for r in runs if "error" not in r]
        meds = [r["median_ms"] for r in good]
        summary[cfg] = {
            "ok_repeats": len(good),
            "median_of_medians_ms": round(statistics.median(meds), 1) if meds else None,
            "spread_ms": round(max(meds) - min(meds), 1) if meds else None,
            "worst_p95_ms": max((r["p95_ms"] for r in good), default=None),
            "rss_peak_mb": max((r["rss_peak_mb"] or 0 for r in good), default=None),
        }
    return summary


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", type=Path, required=True)
    ap.add_argument("--size", type=int, default=416)
    ap.add_argument("--configs", default="1:seq,2:seq,4:seq,2:par")
    ap.add_argument("--runs", type=int, default=40)
    ap.add_argument("--warmup", type=int, default=5)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--label", default="")
    ap.add_argument("--single", help="internal: one config, JSON to --out")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    if a.single:
        result = run_single(a.model, a.size, parse_config(a.single), a.runs, a.warmup)
        a.out.write_text(json.dumps(result))
        return 0
    if not a.model.is_file():
        raise SystemExit(f"model not found: {a.model}")
    configs = [c.strip() for c in a.configs.split(",") if c.strip()]
    for c in configs:
        parse_config(c)
    results: Dict[str, List[Dict[str, Any]]] = {c: [] for c in configs}
    for rep in range(a.repeats):
        for c in configs:  # interleaved so drift (thermal, background load) hits every config alike
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "r.json"
                cmd = [sys.executable, "-m", "scripts.benchmark_ort_threads", "--model", str(a.model),
                       "--size", str(a.size), "--runs", str(a.runs), "--warmup", str(a.warmup),
                       "--single", c, "--out", str(out)]
                p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
                if p.returncode == 0 and out.is_file():
                    res = json.loads(out.read_text())
                else:
                    res = {"error": (p.stderr or "")[-300:]}
            results[c].append(res)
            print(f"repeat {rep + 1}/{a.repeats} {c}: {res}")
    summary = summarize(results)
    print("\nconfig            median-of-medians  spread  worst-p95  rss-peak")
    for c, s in summary.items():
        print(f"{c:16s} {s['median_of_medians_ms']!s:>18} {s['spread_ms']!s:>7} "
              f"{s['worst_p95_ms']!s:>10} {s['rss_peak_mb']!s:>9}")
    print("Configs whose difference is smaller than the spread are NOT distinguishable by this run.")
    report = {"label": a.label, "timestamp": datetime.now().isoformat(timespec="seconds"),
              "python": sys.version.split()[0], "platform": platform.platform(), "model": a.model.name,
              "size": a.size, "runs": a.runs, "repeats": a.repeats, "raw": results, "summary": summary}
    out_dir = ROOT / "results"
    out_dir.mkdir(exist_ok=True)
    path = out_dir / f"ort-threads-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("report:", path)
    return 0 if all(s["ok_repeats"] == a.repeats for s in summary.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())