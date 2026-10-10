"""Bandingkan backend/model deteksi pada input IDENTIK, satu proses per model (RSS bersih).

  python -m scripts.compare_detection_backends --label "X270 AC power" ^
      --spec yolox_nano,models/yolox_nano.onnx,416 ^
      --spec yolo26n_onnx,models/yolo26n.onnx,640 ^
      --spec yolo26n_onnx,models/yolo26s.onnx,640 [--images DIR] [--runs 20] [--warmup 3] [--threads N]

Mengukur latensi dan RAM (seluruh proses). Akurasi butuh ground truth: scripts.eval_detection.
Gambar sintetis tidak berisi objek: jumlah deteksi di sana tidak bermakna.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from core.config import Settings, load_dotenv
from core.detection import create_detection_provider
from scripts.benchmark_detection import ROOT, load_inputs, machine_info, run_benchmark


def parse_spec(spec: str) -> Tuple[str, str, int]:
    parts = [p.strip() for p in spec.split(",")]
    if len(parts) != 3 or not parts[2].isdigit():
        raise SystemExit(f"--spec harus 'backend,path_model,input_size', dapat: {spec!r}")
    return parts[0], parts[1], int(parts[2])


def run_single(spec: str, images: Optional[Path], runs: int, warmup: int, threads: Optional[int]) -> Dict[str, Any]:
    backend, path, size = parse_spec(spec)
    load_dotenv(ROOT / ".env")
    base = Settings.from_env()
    changes: Dict[str, Any] = {"detection_backend": backend, "detection_model_path": path,
                               "detection_input_size": size, "detection_model_sha256": "",
                               "detection_model_id": Path(path).stem[:64]}
    if threads is not None:
        changes["detection_threads"] = threads
    settings = dataclasses.replace(base, **changes)
    return run_benchmark(create_detection_provider(settings), load_inputs(images), settings, runs, warmup)


def summarize(name: str, r: Dict[str, Any]) -> str:
    o = r.get("overall", {})
    stages = {k: v.get("stage_median_ms") for k, v in r.get("per_image", {}).items()}
    first = next(iter(stages.values()), None)
    return (f"{name}: status={r.get('status')} median_ms={o.get('median_ms')} p95_ms={o.get('p95_ms')} "
            f"rss_load_mb={r.get('rss_mb_after_load')} rss_peak_mb={r.get('rss_mb_peak_during_inference')} "
            f"first_ms={r.get('first_inference_ms')} stages(640x480)={first} reason={r.get('reason')}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--spec", action="append", help="backend,path_model,input_size (boleh berulang)")
    ap.add_argument("--single", help="internal: jalankan satu spec dan tulis JSON ke --out")
    ap.add_argument("--images", type=Path, default=None)
    ap.add_argument("--runs", type=int, default=20)
    ap.add_argument("--warmup", type=int, default=3)
    ap.add_argument("--threads", type=int, default=None, help="override VISTA_DETECTION_THREADS (0 = otomatis)")
    ap.add_argument("--label", default="", help="mis. 'X270 AC power, browser tertutup'")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()

    if a.single:  # child process
        result = run_single(a.single, a.images, a.runs, a.warmup, a.threads)
        a.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
        return 0
    if not a.spec:
        ap.error("butuh minimal satu --spec")

    report: Dict[str, Any] = {"label": a.label, "timestamp": datetime.now().isoformat(timespec="seconds"),
                              "machine": machine_info(), "threads_override": a.threads, "results": {}}
    for spec in a.spec:
        parse_spec(spec)  # validasi sebelum memulai proses anak
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "r.json"
            cmd = [sys.executable, "-m", "scripts.compare_detection_backends", "--single", spec,
                   "--runs", str(a.runs), "--warmup", str(a.warmup), "--out", str(out)]
            if a.images:
                cmd += ["--images", str(a.images)]
            if a.threads is not None:
                cmd += ["--threads", str(a.threads)]
            proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
            if proc.returncode != 0 or not out.is_file():
                result = {"status": "child_failed", "reason": (proc.stderr or "")[-500:]}
            else:
                result = json.loads(out.read_text(encoding="utf-8"))
        report["results"][spec] = result
        print(summarize(spec, result))

    target = a.out or ROOT / "results" / f"compare-detection-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("report:", target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())