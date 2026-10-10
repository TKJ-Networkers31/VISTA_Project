"""Download an official YOLOX ONNX model into models/ (opt-in; never runs automatically).

Run:  python -m scripts.fetch_detection_model [--model yolox-nano|yolox-tiny] [--force]

Source: the official YOLOX release assets (github.com/Megvii-BaseDetection/YOLOX, tag 0.1.1rc0). The YOLOX code is
Apache-2.0; the repository does NOT state a separate license for the pretrained weights, which were trained on COCO.
Read docs/DETECTION.md (licensing) and record the owner's decision before distributing anything built on them.

The SHA-256 values below were computed from a download made on 2026-10-09. They detect corruption and later
tampering of the same file; they are NOT checksums published by the YOLOX authors.
models/ and *.onnx are git-ignored: the repository never contains or redistributes the weights.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/"
MODELS: Dict[str, Dict[str, object]] = {
    "yolox-nano": {"file": "yolox_nano.onnx", "bytes": 3_659_407,
                   "sha256": "c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d"},
    "yolox-tiny": {"file": "yolox_tiny.onnx", "bytes": 20_219_662,
                   "sha256": "427cc366d34e27ff7a03e2899b5e3671425c262ea2291f88bb942bc1cc70b0f7"},
}
NOTICE = ("Licensing: YOLOX code is Apache-2.0; no separate license for the pretrained weights is stated upstream "
          "(trained on COCO). See docs/DETECTION.md before redistributing.")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", choices=sorted(MODELS), default="yolox-nano")
    ap.add_argument("--dest", type=Path, default=ROOT / "models")
    ap.add_argument("--force", action="store_true", help="overwrite an existing file")
    args = ap.parse_args(argv)

    spec = MODELS[args.model]
    target = args.dest / str(spec["file"])
    print(NOTICE)
    if target.exists() and not args.force:
        ok = sha256_of(target) == spec["sha256"]
        print(f"{target} already exists ({'checksum OK' if ok else 'CHECKSUM DIFFERS'}); use --force to replace it.")
        return 0 if ok else 1
    args.dest.mkdir(parents=True, exist_ok=True)
    url = BASE + str(spec["file"])
    print(f"downloading {url}")
    fd, tmp_name = tempfile.mkstemp(dir=args.dest, suffix=".part")
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        with urllib.request.urlopen(url, timeout=120) as resp, tmp.open("wb") as out:  # noqa: S310 (fixed https URL)
            while True:
                block = resp.read(1 << 20)
                if not block:
                    break
                out.write(block)
        size, digest = tmp.stat().st_size, sha256_of(tmp)
        if size != spec["bytes"] or digest != spec["sha256"]:
            print(f"REJECTED: size={size} sha256={digest} do not match the pinned values; nothing was installed.")
            return 1
        tmp.replace(target)
    except OSError as exc:
        print(f"download failed: {type(exc).__name__}: {exc}")
        return 2
    finally:
        tmp.unlink(missing_ok=True)
    print(f"installed {target} ({size} bytes, sha256 {digest})")
    print(f"Use it with: VISTA_DETECTION_MODEL_PATH=models/{spec['file']} VISTA_DETECTION_MODEL_ID={args.model}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
