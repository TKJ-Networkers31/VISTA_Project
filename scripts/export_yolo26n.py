"""Export YOLO26n to ONNX FP32. Run ONLY in a separate environment that supports ultralytics/torch.

  py -3.11 -m venv .venv-export ; .\\.venv-export\\Scripts\\python -m pip install ultralytics onnx
  .\\.venv-export\\Scripts\\python scripts\\export_yolo26n.py --imgsz 640

Downloads yolo26n.pt from Ultralytics (explicit, network). Weights: AGPL-3.0 or Enterprise license.
"""
import argparse
import hashlib
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", default="yolo26n.pt")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--dest", type=Path, default=ROOT / "models" / "yolo26n.onnx")
    a = ap.parse_args()
    from ultralytics import YOLO

    path = Path(YOLO(a.weights).export(format="onnx", imgsz=a.imgsz, simplify=True, dynamic=False))
    a.dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, a.dest)
    digest = hashlib.sha256(a.dest.read_bytes()).hexdigest()
    print(f"{a.dest} bytes={a.dest.stat().st_size} sha256={digest}")
    print(f"Then: VISTA_DETECTION_BACKEND=yolo26n_onnx VISTA_DETECTION_MODEL_PATH=models/{a.dest.name} "
          f"VISTA_DETECTION_MODEL_ID={a.dest.stem} VISTA_DETECTION_INPUT_SIZE={a.imgsz} "
          f"VISTA_DETECTION_MODEL_SHA256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())