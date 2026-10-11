"""Diagnose the NVIDIA NIM connection step by step, outside the web page. Run from the repository root:

  python -m scripts.diagnose_nim [--timeout 180] [--image C:\\path\\photo.jpg]

It reads .env like the server does and prints the EFFECTIVE settings (never the key), then sends a few small requests:
text only, then synthetic images of growing size (and your own image if --image is given). Each line shows HTTP result
and seconds, so you can see whether the key works, whether the network works, and from which image size the provider
becomes slow. It sends ONLY synthetic images unless you pass --image. Nothing here proves answer quality.
"""
from __future__ import annotations

import argparse
import io
import json
import time
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageOps

from core.config import Settings, load_dotenv
from core.contracts import VistaError
from core.providers.nim import NimAdapter, NimConfig, _urllib_transport
from core.vision.encode import prepare_jpeg

ROOT = Path(__file__).resolve().parents[1]


def synthetic_jpeg(side: int) -> bytes:
    w, h = side, max(1, round(side * 9 / 16))
    img = Image.new("RGB", (w, h), (240, 240, 240))
    d = ImageDraw.Draw(img)
    d.rectangle([w // 5, h // 5, w * 4 // 5, h * 4 // 5], fill=(200, 30, 30))
    d.ellipse([w // 2, h // 3, w * 3 // 4, h * 2 // 3], fill=(30, 60, 200))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def text_only(cfg: NimConfig, timeout: float) -> str:
    payload = {"model": cfg.model, "stream": False, "max_tokens": 32,
               "chat_template_kwargs": {"enable_thinking": cfg.enable_thinking},
               "messages": [{"role": "user", "content": "Say hi in one word."}]}
    headers = {"Authorization": "Bearer " + cfg.api_key, "Accept": "application/json",
               "Content-Type": "application/json"}
    status, _h, raw = _urllib_transport(cfg.base_url.rstrip("/") + "/chat/completions", headers,
                                        json.dumps(payload).encode(), timeout)
    if status != 200:  # diagnostic only: show the real HTTP status and a short provider message
        snippet = raw[:200].decode("utf-8", "replace").replace("\n", " ")
        raise VistaError("provider_internal", f"HTTP_{status}", f"provider replied: {snippet}")
    return NimAdapter._parse(status, raw)


def run(label: str, fn) -> bool:
    t0 = time.perf_counter()
    try:
        out = fn()
        print(f"[OK ] {label:28s} {time.perf_counter() - t0:6.1f} s  answer={out[:120]!r}")
        return True
    except VistaError as err:
        print(f"[ERR] {label:28s} {time.perf_counter() - t0:6.1f} s  {err.code}: {err.message}")
    except Exception as exc:  # report the type only: messages may carry paths
        print(f"[ERR] {label:28s} {time.perf_counter() - t0:6.1f} s  unexpected {type(exc).__name__}")
    return False


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--timeout", type=float, default=180.0, help="seconds per request (default 180)")
    ap.add_argument("--image", type=Path, default=None, help="optional extra test with your own image")
    ap.add_argument("--question", default="Describe this image briefly.", help="question for --image")
    args = ap.parse_args(argv)

    env_file = ROOT / ".env"
    load_dotenv(env_file)
    s = Settings.from_env()
    print(f".env found: {env_file.is_file()} | external_enabled={s.external_enabled} | "
          f"key set: {bool(s.nim_api_key)} (length {len(s.nim_api_key)}) | model={s.nim_model}")
    print(f"server settings: external_timeout={s.external_timeout_seconds}s retry_max={s.external_retry_max} "
          f"task_timeout={s.task_timeout_seconds}s | this script uses {args.timeout}s per request, no retries")
    if not s.nim_api_key:
        print("No VISTA_NIM_API_KEY in .env: nothing to test.")
        return 2
    cfg = NimConfig(api_key=s.nim_api_key, base_url=s.nim_base_url, model=s.nim_model,
                    timeout_seconds=args.timeout, max_tokens=256, enable_thinking=False, max_retries=0)
    adapter = NimAdapter(cfg)
    results = [run("text only (no image)", lambda: text_only(cfg, args.timeout))]
    for side in (64, 256, 512, 768, 1024):
        jpg = synthetic_jpeg(side)
        results.append(run(f"image {side}px ({len(jpg)} B)",
                           lambda j=jpg: adapter.ask(j, "What colors are the shapes? One short sentence.")))
    if args.image:  # your own image, re-encoded exactly like the server does (JPEG, resized), at several sizes
        src = ImageOps.exif_transpose(Image.open(args.image)).convert("RGB")
        print(f"\nyour image: {src.size[0]}x{src.size[1]} px, question: {args.question!r}")
        for side in (1024, 768, 512):
            jpg, _note = prepare_jpeg(src, side, 10_000_000)
            results.append(run(f"your image <= {side}px ({len(jpg)} B)",
                               lambda j=jpg: adapter.ask(j, args.question)))
    print("\nHow to read this:")
    print("- text only fails with HTTP_401/403: key wrong/inactive. NIM_TIMEOUT/NIM_NETWORK: network or endpoint.")
    print("- text ok but images time out: the vision path is slow; use the smallest size that works, long timeout.")
    print("- everything ok here but the page times out: the server is not using the .env values (see its log).")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
