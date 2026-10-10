"""Reproducible detection evaluation on YOUR labeled images. Offline once the model file is installed.

Run:  python -m scripts.eval_detection --images D:\\eval\\images --annotations D:\\eval\\annotations.json
          [--thresholds 0.2,0.3,0.4,0.5,0.6] [--iou 0.5] [--variants pil:class_aware,cv2:class_aware,pil:agnostic]
          [--label "X270 AC power"] [--out results]

Annotations: COCO JSON (export format of CVAT, Label Studio, makesense.ai, labelme->COCO converters, ...):
  images[{id,file_name,width,height}], annotations[{image_id,category_id,bbox:[x,y,w,h]}], categories[{id,name}].
  * An image with NO annotations is a NEGATIVE image (nothing the model should report). Include plenty of these.
  * Category names that are COCO class names ("laptop", "cell phone", "person", ...) are SUPPORTED and are scored as
    normal detection targets. Any other name (e.g. "calendar", "charger_plug") is OUT-OF-VOCABULARY (OOD): the model
    cannot name it, so every detection on it is a false positive, and the harness records WHICH label it got
    (the "confusions" table). That table measures exactly the "calendar -> laptop" type of error.

Matching: detections sorted by score; a detection is a true positive if it has the same label as a still-unmatched
supported ground-truth box with IoU >= --iou; every other detection is a false positive; unmatched supported
ground-truth boxes are false negatives. Detections are computed ONCE per variant at a low floor threshold and then
filtered per threshold (identical to running at that threshold, because greedy NMS processes boxes by descending score;
the result cap is set high enough not to interfere).

What it does NOT do: it does not compute mAP, it does not pick a threshold for you, and with few images the ratios are
unreliable, so raw counts (tp/fp/fn) are always printed and a warning is shown below 100 supported GT boxes.
Nothing here is a result until you run it on your own labeled set.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
FLOOR = 0.05
OOD_OVERLAP_IOU = 0.3  # a false positive this much on top of an unsupported object counts as a confusion with it

Box = Sequence[float]
Det = Tuple[str, float, Box]  # (label, score, [x1, y1, x2, y2])


# ---------------- pure logic (unit-tested; no model, no images) ----------------
def iou(a: Box, b: Box) -> float:
    iw = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    ih = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = iw * ih
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def load_coco(path: Path) -> List[Dict[str, Any]]:
    """COCO JSON -> [{file, objects: [{label, bbox_xyxy}]}], sorted by file name. Labels are lower-cased."""
    data = json.loads(path.read_text(encoding="utf-8"))
    cats = {c["id"]: str(c["name"]).strip().lower() for c in data.get("categories", [])}
    by_image: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)
    for ann in data.get("annotations", []):
        x, y, w, h = ann["bbox"]
        if w <= 0 or h <= 0:
            raise ValueError(f"annotation with an empty box in image id {ann['image_id']}")
        by_image[ann["image_id"]].append({"label": cats[ann["category_id"]], "bbox": [x, y, x + w, y + h]})
    images = [{"file": im["file_name"], "objects": by_image.get(im["id"], [])} for im in data.get("images", [])]
    return sorted(images, key=lambda r: r["file"])


def evaluate(images: List[Dict[str, Any]], detections: Dict[str, List[Det]], threshold: float, iou_thr: float,
             vocabulary: Sequence[str]) -> Dict[str, Any]:
    vocab = set(vocabulary)
    per_class: Dict[str, Counter] = defaultdict(Counter)
    confusions: Dict[str, Counter] = defaultdict(Counter)
    neg_images = neg_with_det = total_dets = 0
    for im in images:
        gts = [o for o in im["objects"] if o["label"] in vocab]
        ood = [o for o in im["objects"] if o["label"] not in vocab]
        dets = sorted((d for d in detections.get(im["file"], []) if d[1] >= threshold), key=lambda d: -d[1])
        total_dets += len(dets)
        if not im["objects"]:
            neg_images += 1
            neg_with_det += 1 if dets else 0
        used = set()
        for label, _score, box in dets:
            best, best_i = 0.0, None
            for i, g in enumerate(gts):
                if i in used or g["label"] != label:
                    continue
                v = iou(box, g["bbox"])
                if v > best:
                    best, best_i = v, i
            if best_i is not None and best >= iou_thr:
                used.add(best_i)
                per_class[label]["tp"] += 1
                continue
            per_class[label]["fp"] += 1
            overlaps = [(iou(box, o["bbox"]), o["label"]) for o in ood]
            if overlaps and max(overlaps)[0] >= OOD_OVERLAP_IOU:
                confusions[max(overlaps)[1]][label] += 1
        for i, g in enumerate(gts):
            if i not in used:
                per_class[g["label"]]["fn"] += 1

    def ratio(n: float, d: float) -> Optional[float]:
        return round(n / d, 4) if d else None

    tp = sum(c["tp"] for c in per_class.values())
    fp = sum(c["fp"] for c in per_class.values())
    fn = sum(c["fn"] for c in per_class.values())
    return {
        "threshold": threshold, "tp": tp, "fp": fp, "fn": fn, "detections": total_dets,
        "precision": ratio(tp, tp + fp), "recall": ratio(tp, tp + fn),
        "fp_per_image": ratio(fp, len(images)),
        "negative_images": neg_images, "negative_image_false_alarm_rate": ratio(neg_with_det, neg_images),
        "per_class": {k: {**dict(v), "precision": ratio(v["tp"], v["tp"] + v["fp"]),
                          "recall": ratio(v["tp"], v["tp"] + v["fn"])} for k, v in sorted(per_class.items())},
        "confusions_unsupported_to_predicted": {k: dict(v.most_common()) for k, v in sorted(confusions.items())},
    }


def sweep(images, detections, thresholds, iou_thr, vocabulary) -> List[Dict[str, Any]]:
    return [evaluate(images, detections, t, iou_thr, vocabulary) for t in thresholds]


# ---------------- model-backed part ----------------
def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def collect(settings, images_dir: Path, images: List[Dict[str, Any]]) -> Dict[str, List[Det]]:
    from PIL import Image, ImageOps

    from core.detection.yolox_onnx import YoloxOnnxProvider

    provider = YoloxOnnxProvider(settings)
    ok, reason = provider.is_available()
    if not ok:
        raise SystemExit(f"detection backend unavailable: {reason}")
    provider.load()
    out: Dict[str, List[Det]] = {}
    for im in images:
        img = ImageOps.exif_transpose(Image.open(images_dir / im["file"])).convert("RGB")
        raw = provider.detect(img, FLOOR, settings.detection_nms_iou, 300)
        out[im["file"]] = [(d.label, d.confidence, d.bbox) for d in raw.detections]
    return out


def print_table(name: str, rows: List[Dict[str, Any]]) -> None:
    print(f"\n--- {name}")
    print(f"{'thr':>5} {'tp':>5} {'fp':>5} {'fn':>5} {'precision':>10} {'recall':>8} {'fp/img':>7} {'neg-img FPR':>12}")
    for r in rows:
        f = lambda v: "n/a" if v is None else f"{v:.3f}"  # noqa: E731
        print(f"{r['threshold']:>5.2f} {r['tp']:>5} {r['fp']:>5} {r['fn']:>5} {f(r['precision']):>10} "
              f"{f(r['recall']):>8} {f(r['fp_per_image']):>7} {f(r['negative_image_false_alarm_rate']):>12}")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--images", type=Path, required=True)
    ap.add_argument("--annotations", type=Path, required=True)
    ap.add_argument("--thresholds", default="0.2,0.3,0.4,0.5,0.6")
    ap.add_argument("--iou", type=float, default=0.5)
    ap.add_argument("--variants", default="pil:class_aware,cv2:class_aware,pil:agnostic,cv2:agnostic",
                    help="comma list of resize:nms_mode")
    ap.add_argument("--label", default="")
    ap.add_argument("--out", type=Path, default=ROOT / "results")
    args = ap.parse_args(argv)

    import dataclasses

    from core.config import Settings, load_dotenv
    from core.detection.coco_labels import COCO_CLASSES

    load_dotenv(ROOT / ".env")
    base = Settings.from_env()
    thresholds = [float(t) for t in args.thresholds.split(",")]
    images = load_coco(args.annotations)
    missing = [im["file"] for im in images if not (args.images / im["file"]).is_file()]
    if missing:
        raise SystemExit(f"{len(missing)} annotated image(s) missing in --images, e.g. {missing[0]}")
    n_gt = sum(1 for im in images for o in im["objects"] if o["label"] in set(COCO_CLASSES))
    print(f"{len(images)} images, {n_gt} supported GT boxes, "
          f"{sum(1 for im in images if not im['objects'])} negative images")
    if n_gt < 100:
        print("WARNING: fewer than 100 supported ground-truth boxes; ratios below are NOT reliable, read the counts.")

    digest = hashlib.sha256()
    digest.update(args.annotations.read_bytes())
    for im in images:
        digest.update((args.images / im["file"]).read_bytes())
    report: Dict[str, Any] = {
        "label": args.label, "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python": sys.version.split()[0], "platform": platform.platform(), "iou_threshold": args.iou,
        "dataset_sha256": digest.hexdigest(), "n_images": len(images), "n_supported_gt": n_gt,
        "model_id": base.detection_model_id, "nms_iou": base.detection_nms_iou, "variants": {},
    }
    for spec in args.variants.split(","):
        resize, nms_mode = spec.strip().split(":")
        s = dataclasses.replace(base, detection_resize=resize, detection_nms_mode=nms_mode)
        dets = collect(s, args.images, images)
        rows = sweep(images, dets, thresholds, args.iou, COCO_CLASSES)
        report["variants"][spec] = rows
        print_table(spec, rows)
        for r in rows:
            if r["confusions_unsupported_to_predicted"]:
                print(f"  confusions @ {r['threshold']:.2f}: {r['confusions_unsupported_to_predicted']}")
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"eval-detection-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nreport: {path}\ndataset_sha256: {report['dataset_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
