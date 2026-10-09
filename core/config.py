"""Typed, validated settings loaded from environment variables (and an optional .env file).

Invalid values fail fast with a message that names the variable, never its value.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

MIME_TO_FORMAT = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}


class ConfigError(ValueError):
    pass


def load_dotenv(path: Path, environ: Optional[dict] = None) -> None:
    """Minimal .env loader. Existing environment variables win. Values are never printed."""
    environ = os.environ if environ is None else environ
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _int(env: Mapping[str, str], name: str, default: int, minimum: int) -> int:
    raw = env.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError(f"{name} must be an integer") from None
    if value < minimum:
        raise ConfigError(f"{name} must be >= {minimum}")
    return value


@dataclass(frozen=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "INFO"
    max_upload_bytes: int = 10_485_760
    max_image_side: int = 6000
    max_image_pixels: int = 20_000_000
    allowed_mime: tuple = ("image/jpeg", "image/png", "image/webp")
    worker_concurrency: int = 1
    queue_max_size: int = 4
    task_timeout_seconds: int = 60
    ocr_engine: str = "rapidocr"
    ocr_max_side: int = 1600

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "Settings":
        env = os.environ if env is None else env
        mimes = tuple(
            m.strip().lower() for m in (env.get("VISTA_ALLOWED_MIME") or "").split(",") if m.strip()
        ) or cls.allowed_mime
        for m in mimes:
            if m not in MIME_TO_FORMAT:
                raise ConfigError("VISTA_ALLOWED_MIME contains an unsupported type")
        level = (env.get("VISTA_LOG_LEVEL") or "INFO").upper()
        if level not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
            raise ConfigError("VISTA_LOG_LEVEL must be DEBUG, INFO, WARNING or ERROR")
        engine = (env.get("VISTA_OCR_ENGINE") or "rapidocr").lower()
        return cls(
            host=env.get("VISTA_HOST") or "127.0.0.1",
            port=_int(env, "VISTA_PORT", 8000, 1),
            log_level=level,
            max_upload_bytes=_int(env, "VISTA_MAX_UPLOAD_BYTES", 10_485_760, 1),
            max_image_side=_int(env, "VISTA_MAX_IMAGE_SIDE", 6000, 1),
            max_image_pixels=_int(env, "VISTA_MAX_IMAGE_PIXELS", 20_000_000, 1),
            allowed_mime=mimes,
            worker_concurrency=_int(env, "VISTA_WORKER_CONCURRENCY", 1, 1),
            queue_max_size=_int(env, "VISTA_QUEUE_MAX_SIZE", 4, 0),
            task_timeout_seconds=_int(env, "VISTA_TASK_TIMEOUT_SECONDS", 60, 1),
            ocr_engine=engine,
            ocr_max_side=_int(env, "VISTA_OCR_MAX_SIDE", 1600, 64),
        )
