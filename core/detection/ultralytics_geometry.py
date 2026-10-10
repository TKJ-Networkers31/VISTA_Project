"""Letterbox, inverse mapping and post-processing for Ultralytics-style ONNX exports (YOLO26/YOLO11/YOLOv8 layouts).

Assumptions (from Ultralytics export behavior; MUST be re-verified on the real exported file, see
docs/DETECTION_PROVIDERS.md): input RGB, 0..1, NCHW, CENTERED letterbox padded with 114.
Output layouts supported:
  "end2end": [N, 6] = x1, y1, x2, y2, score, class_id in letterboxed-input pixels (NMS already done inside the model)
  "raw":     [4 + C, A] = cx, cy, w, h, class probabilities (no objectness); NMS is done here.
"""
from __future__ import annotations

from typing import Tuple

import numpy as np
from PIL import Image

from . import geometry as g

PAD_VALUE = 114


def letterbox_centered(image_rgb: Image.Image, size: int) -> Tuple[np.ndarray, float, Tuple[int, int]]:
    """-> (float32 [1,3,size,size] RGB 0..1, ratio, (pad_left, pad_top))."""
    if image_rgb.mode != "RGB":
        image_rgb = image_rgb.convert("RGB")
    w, h = image_rgb.size
    if w < 1 or h < 1 or size < 1:
        raise ValueError("width, height and size must be positive")
    ratio = min(size / h, size / w)
    new_w, new_h = max(1, round(w * ratio)), max(1, round(h * ratio))
    left, top = int(round((size - new_w) / 2 - 0.1)), int(round((size - new_h) / 2 - 0.1))
    left, top = max(0, left), max(0, top)
    canvas = np.full((size, size, 3), PAD_VALUE, dtype=np.uint8)
    resized = image_rgb.resize((new_w, new_h), Image.Resampling.BILINEAR)
    canvas[top:top + new_h, left:left + new_w] = np.asarray(resized)
    blob = np.ascontiguousarray(canvas.transpose(2, 0, 1), dtype=np.float32) / 255.0
    return blob[None, ...], ratio, (left, top)


def unmap_boxes(boxes_xyxy: np.ndarray, ratio: float, pad: Tuple[int, int]) -> np.ndarray:
    """Inverse of the letterbox: network pixels -> source-image pixels."""
    if not (ratio > 0 and np.isfinite(ratio)):
        raise ValueError("ratio must be a positive finite number")
    out = boxes_xyxy.astype(np.float64).copy()
    out[:, [0, 2]] = (out[:, [0, 2]] - pad[0]) / ratio
    out[:, [1, 3]] = (out[:, [1, 3]] - pad[1]) / ratio
    return out


def _finish(boxes, scores, ids, ratio, pad, max_detections):
    order = np.argsort(-scores, kind="stable")[:max_detections]
    return unmap_boxes(boxes[order], ratio, pad), scores[order].astype(np.float64), ids[order].astype(np.int64)


def postprocess_end2end(out: np.ndarray, ratio: float, pad: Tuple[int, int], conf: float, max_detections: int):
    if out.ndim != 2 or out.shape[1] != 6:
        raise ValueError("expected [N, 6] end-to-end output")
    valid = np.isfinite(out).all(axis=1) & (out[:, 4] >= conf)
    out = out[valid]
    return _finish(out[:, 0:4], out[:, 4], out[:, 5].astype(np.int64), ratio, pad, max_detections)


def postprocess_raw(out: np.ndarray, ratio: float, pad: Tuple[int, int], conf: float, nms_iou: float,
                    max_detections: int, class_aware: bool = True):
    if out.ndim != 2 or out.shape[0] < 5:
        raise ValueError("expected [4 + classes, anchors] raw output")
    pred = out.T  # [A, 4 + C]
    cls = pred[:, 4:]
    ids = cls.argmax(axis=1)
    scores = cls[np.arange(cls.shape[0]), ids]
    boxes = g.xywh_to_xyxy(pred[:, 0:4])
    valid = np.isfinite(scores) & np.isfinite(boxes).all(axis=1) & (scores >= conf)
    idx = np.flatnonzero(valid)
    if idx.size == 0:
        return np.empty((0, 4)), np.empty((0,)), np.empty((0,), np.int64)
    if idx.size > g.PRE_NMS_TOP_K:
        idx = idx[np.argpartition(-scores[idx], g.PRE_NMS_TOP_K - 1)[:g.PRE_NMS_TOP_K]]
    boxes, scores, ids = boxes[idx], scores[idx], ids[idx]
    keep = (g.class_aware_nms(boxes, scores, ids, nms_iou) if class_aware else g.nms(boxes, scores, nms_iou))
    return _finish(boxes[keep], scores[keep], ids[keep], ratio, pad, max_detections)