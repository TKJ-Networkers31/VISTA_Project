"""Re-encode an already validated image as a small JPEG for external transmission (bounded size, no metadata)."""
from __future__ import annotations

import io
from typing import Tuple

from PIL import Image

from core.contracts import VistaError

SIDES = (1024, 768, 512, 384, 256)
QUALITIES = (85, 70, 55)


def prepare_jpeg(image: Image.Image, max_side: int, limit_bytes: int) -> Tuple[bytes, str]:
    """-> (jpeg bytes <= limit_bytes, human note). EXIF/metadata are dropped by re-encoding from pixels only."""
    if image.mode != "RGB":
        image = image.convert("RGB")
    width, height = image.size
    sides = [s for s in dict.fromkeys((max_side, *SIDES)) if s <= max_side]
    for side in sides:
        k = min(1.0, side / max(width, height))
        work = image if k >= 1.0 else image.resize((max(1, round(width * k)), max(1, round(height * k))),
                                                   Image.Resampling.LANCZOS)
        for quality in QUALITIES:
            buf = io.BytesIO()
            work.save(buf, "JPEG", quality=quality, optimize=True)
            if buf.tell() <= limit_bytes:
                note = (f"Image re-encoded as JPEG {work.size[0]}x{work.size[1]} (quality {quality}, "
                        f"{buf.tell()} bytes) before external transmission.")
                return buf.getvalue(), note
    raise VistaError("invalid_input", "IMAGE_TOO_LARGE_FOR_PROVIDER",
                     "The image could not be reduced below the external provider's size limit.",
                     details={"limit_bytes": limit_bytes})
