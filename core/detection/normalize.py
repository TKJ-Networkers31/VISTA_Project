"""Turn raw backend detections into validated contract objects in original-image pixels.

The backend is not trusted: anything non-finite, unlabeled, out of range or degenerate is dropped and counted in a
warning, never repaired or invented.
"""
from __future__ import annotations

import math
from typing import List, Tuple

from core.contracts import Detection
from core.providers import RawDetectionResult


def normalize_detections(raw: RawDetectionResult, width: int, height: int,
                         max_detections: int) -> Tuple[List[Detection], List[str]]:
    """Clip boxes to [0, width] x [0, height], drop invalid entries, sort by confidence, cap the count."""
    kept: List[Detection] = []
    dropped = 0
    for item in raw.detections:
        try:
            conf = float(item.confidence)
            box = [float(v) for v in item.bbox]
            class_id = int(item.class_id)
        except (TypeError, ValueError):
            dropped += 1
            continue
        label = (item.label or "").strip()
        if len(box) != 4 or not label or class_id < 0 or not math.isfinite(conf) or not 0.0 <= conf <= 1.0:
            dropped += 1
            continue
        if not all(math.isfinite(v) for v in box):
            dropped += 1
            continue
        x1 = round(min(max(box[0], 0.0), float(width)), 1)
        y1 = round(min(max(box[1], 0.0), float(height)), 1)
        x2 = round(min(max(box[2], 0.0), float(width)), 1)
        y2 = round(min(max(box[3], 0.0), float(height)), 1)
        if x2 <= x1 or y2 <= y1:  # inverted, empty, or entirely outside the image
            dropped += 1
            continue
        kept.append(Detection(class_id=class_id, label=label, confidence=round(conf, 4), bbox2d=[x1, y1, x2, y2]))
    kept.sort(key=lambda d: d.confidence, reverse=True)  # stable: equal scores keep backend order
    warnings: List[str] = []
    if dropped:
        warnings.append(f"{dropped} backend detection(s) were discarded because their class, score or box was invalid.")
    if len(kept) > max_detections:
        kept = kept[:max_detections]
    return kept, warnings
