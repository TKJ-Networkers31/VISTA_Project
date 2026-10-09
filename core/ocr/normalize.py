"""Turn raw engine output into contract blocks: pixel mapping, reading order, joined text."""
from __future__ import annotations

from statistics import mean
from typing import List, Tuple

from core.contracts import OCRBlock
from core.providers import RawOCRResult


def raw_to_dicts(raw: RawOCRResult) -> list:
    return [{"text": i.text, "polygon": i.polygon, "confidence": i.confidence} for i in raw.items]


def normalize(raw: RawOCRResult, sx: float, sy: float, width: int, height: int) -> Tuple[List[OCRBlock], str]:
    """sx, sy map inference-image pixels back to original pixels (original / inference)."""
    cands = []
    for item in raw.items:
        text = item.text.strip()
        if not text:
            continue
        poly = bbox = None
        if item.polygon:
            poly = [[round(x * sx, 1), round(y * sy, 1)] for x, y in item.polygon]
            xs, ys = [p[0] for p in poly], [p[1] for p in poly]
            bbox = [max(0.0, min(xs)), max(0.0, min(ys)), min(float(width), max(xs)), min(float(height), max(ys))]
        conf = item.confidence if item.confidence is not None and 0.0 <= item.confidence <= 1.0 else None
        cands.append((text, poly, bbox, conf))

    with_box = sorted((c for c in cands if c[2]), key=lambda c: c[2][1])
    without_box = [c for c in cands if not c[2]]  # keep engine order, appended last

    lines: List[List[tuple]] = []
    for c in with_box:
        cy, h = (c[2][1] + c[2][3]) / 2, max(c[2][3] - c[2][1], 1.0)
        for line in lines:
            lcy = mean((b[2][1] + b[2][3]) / 2 for b in line)
            lh = mean(max(b[2][3] - b[2][1], 1.0) for b in line)
            if abs(cy - lcy) < 0.5 * min(h, lh):
                line.append(c)
                break
        else:
            lines.append([c])

    blocks: List[OCRBlock] = []
    text_lines: List[str] = []
    for idx, line in enumerate(sorted(lines, key=lambda ln: mean(b[2][1] for b in ln))):
        line.sort(key=lambda b: b[2][0])
        for text, poly, bbox, conf in line:
            blocks.append(OCRBlock(text=text, bbox2d=[round(v, 1) for v in bbox], polygon=poly,
                                   confidence=conf, line_index=idx))
        text_lines.append(" ".join(b[0] for b in line))
    base = len(lines)
    for j, (text, _poly, _bbox, conf) in enumerate(without_box):
        blocks.append(OCRBlock(text=text, bbox2d=None, polygon=None, confidence=conf, line_index=base + j))
        text_lines.append(text)
    return blocks, "\n".join(text_lines)
