"""Upload validation and decoding. Verifies by decoding, never by extension or client MIME alone."""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import List, Optional

from PIL import Image, ImageOps, UnidentifiedImageError

from core.contracts import VistaError


@dataclass(frozen=True)
class ImageLimits:
    max_bytes: int
    max_side: int
    max_pixels: int
    allowed_formats: frozenset  # e.g. {"JPEG", "PNG", "WEBP"}
    allowed_mime: frozenset


@dataclass
class DecodedImage:
    image: Image.Image  # RGB, EXIF-oriented
    width: int
    height: int
    format: str
    warnings: List[str] = field(default_factory=list)


def _bad(code: str, message: str, **details) -> VistaError:
    return VistaError("invalid_input", code, message, retryable=False, details=details)


def decode_image(data: bytes, declared_mime: Optional[str], limits: ImageLimits) -> DecodedImage:
    if not data:
        raise _bad("EMPTY_FILE", "The uploaded file is empty.")
    if len(data) > limits.max_bytes:
        raise _bad("IMAGE_TOO_LARGE", "The file exceeds the configured size limit.", limit_bytes=limits.max_bytes)

    mime = (declared_mime or "").split(";")[0].strip().lower()
    if mime and mime != "application/octet-stream" and mime not in limits.allowed_mime:
        raise _bad("UNSUPPORTED_FORMAT", "File type is not supported.", allowed=sorted(limits.allowed_mime))

    try:
        img = Image.open(io.BytesIO(data))  # reads the header only
    except UnidentifiedImageError:
        raise _bad("UNSUPPORTED_FORMAT", "The file is not a supported image.",
                   allowed=sorted(limits.allowed_mime)) from None
    except Image.DecompressionBombError:
        raise _bad("IMAGE_DIMENSIONS_EXCEEDED", "Image dimensions exceed the configured limit.") from None
    except Exception:
        raise _bad("CORRUPT_IMAGE", "The image could not be read.") from None

    fmt = (img.format or "").upper()
    if fmt not in limits.allowed_formats:
        raise _bad("UNSUPPORTED_FORMAT", "Image format is not supported.", allowed=sorted(limits.allowed_mime))

    w, h = img.size
    if max(w, h) > limits.max_side or w * h > limits.max_pixels:
        raise _bad("IMAGE_DIMENSIONS_EXCEEDED", "Image dimensions exceed the configured limit.",
                   max_side=limits.max_side, max_pixels=limits.max_pixels)

    warnings: List[str] = []
    try:
        n_frames = getattr(img, "n_frames", 1)
        img.load()  # full decode, only after limits passed
    except Image.DecompressionBombError:
        raise _bad("IMAGE_DIMENSIONS_EXCEEDED", "Image dimensions exceed the configured limit.") from None
    except Exception:
        raise _bad("CORRUPT_IMAGE", "The image is corrupt or truncated.") from None
    if n_frames > 1:
        warnings.append("Multi-frame image: only the first frame was processed.")

    try:
        oriented = ImageOps.exif_transpose(img)
        if oriented.size != img.size:
            warnings.append("EXIF orientation applied; coordinates refer to the rotated image.")
        img = oriented
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            rgba = img.convert("RGBA")
            bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            img = Image.alpha_composite(bg, rgba).convert("RGB")
        else:
            img = img.convert("RGB")
    except Exception:
        raise _bad("CORRUPT_IMAGE", "The image could not be converted.") from None

    return DecodedImage(image=img, width=img.size[0], height=img.size[1], format=fmt, warnings=warnings)
