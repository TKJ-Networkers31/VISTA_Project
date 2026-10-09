"""Black-box probes against a real server process: backpressure, timeout/drain, temp files, limits, shutdown.

Run:  python -m scripts.probe_server [--keep-going]
Starts its own server on a free localhost port using the real OCR engine (offline, no downloads).
Verdicts: PASS / FAIL / INCONCLUSIVE (the machine was too fast/slow to trigger the condition). Not a load test.
Windows shutdown uses CTRL_BREAK_EVENT; that path is UNVERIFIED until run on Windows.
"""
from __future__ import annotations

import argparse
import http.client
import io
import json
import os
import platform
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"
BOUNDARY = "----vistaprobe"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def multipart(data: bytes, name: str = "probe.png") -> tuple:
    body = (f'--{BOUNDARY}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
            f"Content-Type: image/png\r\n\r\n").encode() + data + f"\r\n--{BOUNDARY}--\r\n".encode()
    return body, {"Content-Type": f"multipart/form-data; boundary={BOUNDARY}"}


def post(port: int, data: bytes, timeout: float = 120) -> tuple:
    body, headers = multipart(data)
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/v1/ocr", data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.load(e)
        except Exception:
            return e.code, {}
    except Exception as e:  # connection reset etc.
        return -1, {"exception": type(e).__name__}


def health(port: int) -> Optional[dict]:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as r:
            return json.load(r)
    except Exception:
        return None


class Server:
    def __init__(self, **env) -> None:
        self.port = free_port()
        self.env = {**os.environ, "VISTA_PORT": str(self.port), "VISTA_HOST": "127.0.0.1", "VISTA_LOG_LEVEL": "WARNING",
                    **{k: str(v) for k, v in env.items()}}
        self.proc: Optional[subprocess.Popen] = None
        self.peak_rss_mb: Optional[float] = None
        self._stop = threading.Event()

    def __enter__(self):
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if platform.system() == "Windows" else 0
        self.proc = subprocess.Popen([sys.executable, "-m", "apps.api"], cwd=ROOT, env=self.env, creationflags=flags,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            if health(self.port):
                break
            time.sleep(0.2)
        else:
            raise RuntimeError("server did not start")
        threading.Thread(target=self._sample, daemon=True).start()
        return self

    def _sample(self) -> None:
        try:
            import psutil
            p = psutil.Process(self.proc.pid)
        except Exception:
            return
        while not self._stop.is_set() and self.proc.poll() is None:
            try:
                v = p.memory_info().rss / 1048576
                self.peak_rss_mb = max(self.peak_rss_mb or 0, round(v, 1))
            except Exception:
                return
            time.sleep(0.1)

    def stop_signal(self) -> None:
        if platform.system() == "Windows":
            self.proc.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            self.proc.send_signal(signal.SIGINT)

    def __exit__(self, *exc):
        self._stop.set()
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def drain(port: int, limit: float = 90) -> Optional[float]:
    t0 = time.time()
    while time.time() - t0 < limit:
        h = health(port)
        if h and h["queue"]["inflight"] == 0:
            return round(time.time() - t0, 1)
        time.sleep(0.25)
    return None


# ---------------- probes ----------------
def probe_backpressure() -> Dict:
    big = (FIX / "large_downscale.png").read_bytes()
    with Server(VISTA_WORKER_CONCURRENCY=1, VISTA_QUEUE_MAX_SIZE=2, VISTA_TASK_TIMEOUT_SECONDS=120) as s:
        res: List[int] = []
        ts = [threading.Thread(target=lambda: res.append(post(s.port, big)[0])) for _ in range(10)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        drained = drain(s.port)
        c = Counter(res)
        ok = set(c) <= {200, 429} and c[200] >= 1 and drained is not None
        verdict = "PASS" if ok and c[429] >= 1 else ("INCONCLUSIVE" if ok else "FAIL")
        return {"verdict": verdict, "status_counts": dict(c), "expected": "capacity 3 => 200s and 429s only",
                "drained_to_inflight_0_s": drained, "server_peak_rss_mb": s.peak_rss_mb}


def probe_timeout_and_drain() -> Dict:
    big = (FIX / "large_downscale.png").read_bytes()
    with Server(VISTA_WORKER_CONCURRENCY=1, VISTA_QUEUE_MAX_SIZE=8, VISTA_TASK_TIMEOUT_SECONDS=1) as s:
        out: List[tuple] = []
        ts = [threading.Thread(target=lambda: out.append(post(s.port, big))) for _ in range(8)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        codes = Counter((st, (b.get("error") or {}).get("code")) for st, b in out)
        drained = drain(s.port)
        after = post(s.port, big)[0]
        timeouts = sum(v for (st, code), v in codes.items() if code == "TASK_TIMEOUT")
        ok = drained is not None and after in (200, 504)
        verdict = "FAIL" if not ok else ("PASS" if timeouts else "INCONCLUSIVE (no request exceeded 1 s)")
        return {"verdict": verdict, "results": {f"{k[0]}/{k[1]}": v for k, v in codes.items()}, "timeouts": timeouts,
                "drained_to_inflight_0_s": drained, "request_after_drain_status": after}


def probe_temp_files() -> Dict:
    import random

    from PIL import Image
    rnd = random.Random(1)
    noisy = Image.frombytes("RGB", (700, 700), bytes(rnd.getrandbits(8) for _ in range(700 * 700 * 3)))
    buf = io.BytesIO()
    noisy.save(buf, "PNG")
    data = buf.getvalue()
    with tempfile.TemporaryDirectory() as tmp:
        with Server(TMPDIR=tmp, TEMP=tmp, TMP=tmp) as s:
            warm = post(s.port, (FIX / "blank.png").read_bytes())[0]  # loads the engine first
            before = sorted(p.name for p in Path(tmp).iterdir())  # engine/library artifacts (see note)
            codes = [post(s.port, data)[0] for _ in range(3)]
            after = sorted(p.name for p in Path(tmp).iterdir())
        created = sorted(set(after) - set(before))
        ok = created == [] and set(codes) == {200} and warm == 200
        return {"verdict": "PASS" if ok else "FAIL", "upload_bytes": len(data), "status_codes": codes,
                "files_created_by_uploads": created, "files_present_before_uploads": before,
                "note": "files present before uploads come from library import/engine load (e.g. onnxruntime '.ses'), "
                        "not from uploads"}


def probe_limits() -> Dict:
    with Server(VISTA_MAX_UPLOAD_BYTES=100_000) as s:
        # 1) declared Content-Length far above the limit: rejected without sending the body
        c = http.client.HTTPConnection("127.0.0.1", s.port, timeout=10)
        c.putrequest("POST", "/api/v1/ocr")
        c.putheader("Content-Type", f"multipart/form-data; boundary={BOUNDARY}")
        c.putheader("Content-Length", "500000000")
        c.endheaders()
        r1 = c.getresponse()
        s1 = r1.status
        c.close()
        # 2) chunked upload (no Content-Length)
        c = http.client.HTTPConnection("127.0.0.1", s.port, timeout=10)
        c.request("POST", "/api/v1/ocr", body=iter([b"abc"]), encode_chunked=True,
                  headers={"Content-Type": f"multipart/form-data; boundary={BOUNDARY}"})
        s2 = c.getresponse().status
        c.close()
        ok = s1 == 413 and s2 == 411 and health(s.port) is not None
        return {"verdict": "PASS" if ok else "FAIL", "oversize_declared_status": s1, "chunked_status": s2}


def probe_shutdown() -> Dict:
    big = (FIX / "large_downscale.png").read_bytes()
    with Server() as s:
        res: List[tuple] = []
        t = threading.Thread(target=lambda: res.append(post(s.port, big)))
        t.start()
        time.sleep(0.4)  # request is in flight
        t0 = time.time()
        s.stop_signal()
        try:
            code = s.proc.wait(30)
            took = round(time.time() - t0, 1)
            verdict = "PASS" if took < 20 else "FAIL"
        except subprocess.TimeoutExpired:
            code, took, verdict = None, None, "FAIL (still running after 30 s)"
        t.join(30)
        return {"verdict": verdict, "exit_seconds_after_signal": took, "exit_code": code,
                "in_flight_request_result": res[0][0] if res else None,
                "note": "exit code semantics differ on Windows (CTRL_BREAK); verify manually"}


PROBES = {"backpressure": probe_backpressure, "timeout_drain": probe_timeout_and_drain, "temp_files": probe_temp_files,
          "limits": probe_limits, "shutdown": probe_shutdown}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", choices=list(PROBES))
    ap.add_argument("--out", type=Path, default=ROOT / "results")
    args = ap.parse_args()
    report = {"python": sys.version.split()[0], "platform": platform.platform(), "probes": {}}
    for name, fn in PROBES.items():
        if args.only and args.only != name:
            continue
        try:
            report["probes"][name] = fn()
        except Exception as exc:
            report["probes"][name] = {"verdict": "FAIL", "exception": f"{type(exc).__name__}: {exc}"}
        print(f"[{report['probes'][name]['verdict']}] {name}: {json.dumps(report['probes'][name])}")
    args.out.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = args.out / f"probe-{platform.system().lower()}-py{platform.python_version()}-{stamp}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("report:", path)
    return 1 if any(p["verdict"].startswith("FAIL") for p in report["probes"].values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
