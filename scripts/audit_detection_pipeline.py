"""Pipeline audit with the REAL model on YOUR images. Offline; needs models/yolox_nano.onnx and onnxruntime.

Run:  python -m scripts.audit_detection_pipeline --image C:\\path\\a.jpg [--image b.jpg ...]
          [--model models\\yolox_nano.onnx]

It prints (nothing is invented; every number comes from running the model):
  1. model input/output signature and the value ranges of the raw head output (objectness / class columns must be
     probabilities in 0..1, otherwise the decode assumptions are wrong),
  2. for each image, the detections of the current pipeline and of variants that differ in ONE aspect:
     resize backend (pil vs cv2), NMS (class-aware vs agnostic), and a DIAGNOSTIC RGB-instead-of-BGR input.
A variant that scores clearly higher than the current pipeline is a lead to measure on a labeled set
(scripts/eval_detection.py), not proof of better accuracy.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Optional

import numpy as np
from PIL import Image

from core.detection import geometry as g
from core.detection.coco_labels import COCO_CLASSES

ROOT = Path(__file__).resolve().parents[1]


def run_variant(session, name: str, img: Image.Image, size: int, resize: str, nms_mode: str, swap_rgb: bool,
                conf: float):
    blob, ratio = g.letterbox_image(img, size, resize)
    if swap_rgb:
        blob = np.ascontiguousarray(blob[:, ::-1])  # DIAGNOSTIC: feed RGB instead of BGR
    raw = np.asarray(session.run(None, {session.get_inputs()[0].name: blob})[0])[0]
    boxes, scores, ids = g.postprocess_yolox(raw, size, ratio, conf, 0.45, 100, nms_mode)
    return raw, [(COCO_CLASSES[int(i)], float(s), [round(float(v), 1) for v in b])
                 for b, s, i in zip(boxes, scores, ids, strict=True)]


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--image", type=Path, action="append", required=True)
    ap.add_argument("--model", type=Path, default=ROOT / "models" / "yolox_nano.onnx")
    ap.add_argument("--size", type=int, default=416)
    ap.add_argument("--conf", type=float, default=0.30)
    args = ap.parse_args(argv)

    import onnxruntime as ort

    session = ort.InferenceSession(str(args.model), providers=["CPUExecutionProvider"])
    i, o = session.get_inputs()[0], session.get_outputs()[0]
    print(f"input  {i.name} {i.shape} {i.type}")
    print(f"output {o.name} {o.shape} {o.type}  (labels in code: {len(COCO_CLASSES)})")
    variants = [("current: pil + class-aware NMS", "pil", "class_aware", False),
                ("cv2 resize + class-aware NMS", "cv2", "class_aware", False),
                ("pil + agnostic NMS", "pil", "agnostic", False),
                ("cv2 + agnostic NMS", "cv2", "agnostic", False),
                ("DIAGNOSTIC rgb input (pil, class-aware)", "pil", "class_aware", True)]
    for path in args.image:
        img = Image.open(path).convert("RGB")
        print(f"\n=== {path.name} {img.size[0]}x{img.size[1]}")
        for k, (name, resize, nms_mode, swap) in enumerate(variants):
            raw, dets = run_variant(session, name, img, args.size, resize, nms_mode, swap, args.conf)
            if k == 0:
                print(f"raw head: shape={raw.shape} objectness[{raw[:, 4].min():.4f},{raw[:, 4].max():.4f}] "
                      f"classes[{raw[:, 5:].min():.4f},{raw[:, 5:].max():.4f}]")
            print(f"- {name}: {len(dets)} detection(s) >= {args.conf}")
            for label, score, box in dets:
                print(f"    {label:14s} {score:.3f} {box}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
