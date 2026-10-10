"""Letterbox preprocessing, YOLOX head decoding, NMS and box mapping. Pure numpy/Pillow; no ONNX Runtime.

Conventions (match the reference YOLOX deployment code):
- The image is resized by ONE ratio `r = min(S / height, S / width)` and pasted at the TOP-LEFT of an SxS canvas
  filled with 114; the padding is therefore only on the right and/or bottom.
- Network input is BGR, channels-first, float32 in 0..255 (no mean/std).
- Boxes in the network's pixel space are mapped back to the source image by dividing by `r`.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Tuple

import numpy as np
from PIL import Image

PAD_VALUE = 114
STRIDES = (8, 16, 32)
PRE_NMS_TOP_K = 1000  # candidates kept (by score) before NMS; bounds the NMS loop on pathological outputs


def letterbox_size(width: int, height: int, size: int) -> Tuple[int, int, float]:
    """Return (new_width, new_height, ratio) for fitting width x height into a size x size canvas."""
    if width < 1 or height < 1 or size < 1:
        raise ValueError("width, height and size must be positive")
    ratio = min(size / height, size / width)
    return max(1, int(width * ratio)), max(1, int(height * ratio)), ratio


def letterbox_image(image_rgb: Image.Image, size: int) -> Tuple[np.ndarray, float]:
    """PIL RGB image -> (float32 array [1, 3, size, size] in BGR 0..255, ratio)."""
    if image_rgb.mode != "RGB":
        image_rgb = image_rgb.convert("RGB")
    width, height = image_rgb.size
    new_w, new_h, ratio = letterbox_size(width, height, size)
    resized = image_rgb.resize((new_w, new_h), Image.Resampling.BILINEAR)
    canvas = np.full((size, size, 3), PAD_VALUE, dtype=np.uint8)
    canvas[:new_h, :new_w] = np.asarray(resized)[:, :, ::-1]  # RGB -> BGR
    blob = np.ascontiguousarray(canvas.transpose(2, 0, 1), dtype=np.float32)
    return blob[None, ...], ratio


@lru_cache(maxsize=8)
def _grid_and_strides(size: int, strides: Tuple[int, ...]) -> Tuple[np.ndarray, np.ndarray]:
    grids, expanded = [], []
    for stride in strides:
        h = w = size // stride
        xv, yv = np.meshgrid(np.arange(w), np.arange(h))
        grid = np.stack((xv, yv), axis=2).reshape(-1, 2)
        grids.append(grid)
        expanded.append(np.full((grid.shape[0], 1), stride))
    grid_all = np.concatenate(grids, axis=0).astype(np.float32)
    stride_all = np.concatenate(expanded, axis=0).astype(np.float32)
    grid_all.setflags(write=False)
    stride_all.setflags(write=False)
    return grid_all, stride_all


def expected_anchor_count(size: int, strides: Tuple[int, ...] = STRIDES) -> int:
    return sum((size // s) ** 2 for s in strides)


def decode_yolox(raw: np.ndarray, size: int, strides: Tuple[int, ...] = STRIDES) -> np.ndarray:
    """Decode RAW YOLOX head output [A, 5 + C] into (cx, cy, w, h, objectness, class scores...) in network pixels.

    Does not modify `raw`. Raises ValueError if the anchor count does not match `size`.
    """
    if raw.ndim != 2 or raw.shape[1] < 6:
        raise ValueError("expected a 2-D array [anchors, 5 + num_classes]")
    grid, stride = _grid_and_strides(size, tuple(strides))
    if raw.shape[0] != grid.shape[0]:
        raise ValueError("anchor count does not match the configured input size")
    out = np.array(raw, dtype=np.float32, copy=True)
    with np.errstate(over="ignore", invalid="ignore"):
        out[:, 0:2] = (out[:, 0:2] + grid) * stride
        out[:, 2:4] = np.exp(out[:, 2:4]) * stride
    return out


def xywh_to_xyxy(boxes: np.ndarray) -> np.ndarray:
    out = np.empty_like(boxes)
    out[:, 0] = boxes[:, 0] - boxes[:, 2] / 2.0
    out[:, 1] = boxes[:, 1] - boxes[:, 3] / 2.0
    out[:, 2] = boxes[:, 0] + boxes[:, 2] / 2.0
    out[:, 3] = boxes[:, 1] + boxes[:, 3] / 2.0
    return out


def nms(boxes: np.ndarray, scores: np.ndarray, iou_threshold: float) -> np.ndarray:
    """Greedy single-class NMS on xyxy boxes. Returns kept indices, highest score first. Ties keep input order."""
    if boxes.shape[0] == 0:
        return np.empty((0,), dtype=np.int64)
    b = boxes.astype(np.float64)
    x1, y1, x2, y2 = b[:, 0], b[:, 1], b[:, 2], b[:, 3]
    areas = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    order = np.argsort(-scores, kind="stable")
    keep = []
    while order.size > 0:
        i = int(order[0])
        keep.append(i)
        rest = order[1:]
        if rest.size == 0:
            break
        inter_w = np.clip(np.minimum(x2[i], x2[rest]) - np.maximum(x1[i], x1[rest]), 0, None)
        inter_h = np.clip(np.minimum(y2[i], y2[rest]) - np.maximum(y1[i], y1[rest]), 0, None)
        inter = inter_w * inter_h
        union = areas[i] + areas[rest] - inter
        iou = np.divide(inter, union, out=np.zeros_like(inter), where=union > 0)
        order = rest[iou <= iou_threshold]
    return np.asarray(keep, dtype=np.int64)


def class_aware_nms(boxes: np.ndarray, scores: np.ndarray, class_ids: np.ndarray, iou_threshold: float) -> np.ndarray:
    """NMS applied independently per class (boxes of different classes never suppress each other)."""
    if boxes.shape[0] == 0:
        return np.empty((0,), dtype=np.int64)
    offset = (boxes.max() + 1.0) * class_ids.astype(np.float64)
    shifted = boxes.astype(np.float64) + offset[:, None]
    return nms(shifted, scores, iou_threshold)


def postprocess_yolox(raw: np.ndarray, size: int, ratio: float, conf_threshold: float, nms_iou: float,
                      max_detections: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """RAW YOLOX output [A, 5 + C] -> (boxes_xyxy [N, 4] in SOURCE-image pixels, scores [N], class_ids [N]).

    score = objectness x best class probability (one class per anchor), as in the reference implementation.
    Non-finite values are discarded, never repaired. Result is sorted by score, highest first, at most
    `max_detections` long. Boxes are clipped to the network canvas only; clipping to the real image happens in
    `core.detection.normalize`.
    """
    if not (ratio > 0 and np.isfinite(ratio)):
        raise ValueError("ratio must be a positive finite number")
    pred = decode_yolox(raw, size)
    obj = pred[:, 4]
    cls_scores = pred[:, 5:]
    class_ids = cls_scores.argmax(axis=1)
    with np.errstate(invalid="ignore", over="ignore"):  # non-finite products are discarded just below
        scores = obj * cls_scores[np.arange(cls_scores.shape[0]), class_ids]
    boxes = xywh_to_xyxy(pred[:, 0:4])

    valid = np.isfinite(scores) & np.isfinite(boxes).all(axis=1) & (scores >= conf_threshold)
    idx = np.flatnonzero(valid)
    if idx.size == 0:
        return np.empty((0, 4), np.float64), np.empty((0,), np.float64), np.empty((0,), np.int64)
    if idx.size > PRE_NMS_TOP_K:
        top = np.argpartition(-scores[idx], PRE_NMS_TOP_K - 1)[:PRE_NMS_TOP_K]
        idx = idx[top]
    boxes, scores, class_ids = np.clip(boxes[idx], 0.0, float(size)), scores[idx], class_ids[idx]

    keep = class_aware_nms(boxes, scores, class_ids, nms_iou)[:max_detections]
    boxes_src = boxes[keep].astype(np.float64) / ratio
    return boxes_src, scores[keep].astype(np.float64), class_ids[keep].astype(np.int64)
