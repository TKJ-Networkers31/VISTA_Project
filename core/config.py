"""Typed, validated settings loaded from environment variables (and an optional .env file).

Invalid values fail fast with a message that names the variable, never its value.
"""
from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

MIME_TO_FORMAT = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
DETECTION_BACKENDS = ("yolox-onnx",)
DETECTION_RESIZE_MODES = ("pil", "cv2")  # see core/detection/geometry.py
DETECTION_NMS_MODES = ("class_aware", "agnostic")
_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


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


def _float(env: Mapping[str, str], name: str, default: float, minimum: float, maximum: float) -> float:
    raw = env.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = float(raw)
    except ValueError:
        raise ConfigError(f"{name} must be a number") from None
    if not math.isfinite(value):
        raise ConfigError(f"{name} must be a finite number")
    if value < minimum or value > maximum:
        raise ConfigError(f"{name} must be between {minimum} and {maximum}")
    return value


def _bool(env: Mapping[str, str], name: str, default: bool) -> bool:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    value = raw.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ConfigError(f"{name} must be true or false")


def _choice(env: Mapping[str, str], name: str, default: str, allowed: tuple) -> str:
    value = (env.get(name) or default).strip().lower()
    if value not in allowed:
        raise ConfigError(f"{name} must be one of: " + ", ".join(allowed))
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
    # --- model residency (shared by OCR and detection) ---
    max_resident_models: int = 1
    model_acquire_timeout_seconds: int = 30
    # --- object detection (Phase 3) ---
    detection_enabled: bool = True
    detection_backend: str = "yolox-onnx"
    detection_model_path: str = "models/yolox_nano.onnx"  # relative paths resolve against the repository root
    detection_model_id: str = "yolox-nano"  # free-text label echoed in responses; keep it truthful
    detection_model_sha256: str = ""  # optional pin; empty means "do not verify"
    detection_input_size: int = 416  # must equal the model's fixed input size (multiple of 32)
    detection_conf_threshold: float = 0.30
    detection_nms_iou: float = 0.45
    detection_max_detections: int = 100
    detection_threads: int = 0  # 0 = let ONNX Runtime decide
    # --- pipeline variants for accuracy evaluation (defaults = behavior before the audit) ---
    detection_resize: str = "pil"  # "pil" | "cv2"
    detection_nms_mode: str = "class_aware"  # "class_aware" | "agnostic"

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

        backend = (env.get("VISTA_DETECTION_BACKEND") or "yolox-onnx").strip().lower()
        if backend not in DETECTION_BACKENDS:
            raise ConfigError("VISTA_DETECTION_BACKEND must be one of: " + ", ".join(DETECTION_BACKENDS))
        input_size = _int(env, "VISTA_DETECTION_INPUT_SIZE", 416, 32)
        if input_size % 32 != 0 or input_size > 2048:
            raise ConfigError("VISTA_DETECTION_INPUT_SIZE must be a multiple of 32 and at most 2048")
        sha256 = (env.get("VISTA_DETECTION_MODEL_SHA256") or "").strip().lower()
        if sha256 and not _SHA256.match(sha256):
            raise ConfigError("VISTA_DETECTION_MODEL_SHA256 must be empty or 64 hexadecimal characters")
        model_path = (env.get("VISTA_DETECTION_MODEL_PATH") or "models/yolox_nano.onnx").strip()
        model_id = (env.get("VISTA_DETECTION_MODEL_ID") or "yolox-nano").strip()
        if not model_path or "\x00" in model_path:
            raise ConfigError("VISTA_DETECTION_MODEL_PATH is not a valid path")
        if not model_id or len(model_id) > 64:
            raise ConfigError("VISTA_DETECTION_MODEL_ID must be 1-64 characters")

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
            max_resident_models=_int(env, "VISTA_MAX_RESIDENT_MODELS", 1, 1),
            model_acquire_timeout_seconds=_int(env, "VISTA_MODEL_ACQUIRE_TIMEOUT_SECONDS", 30, 1),
            detection_enabled=_bool(env, "VISTA_DETECTION_ENABLED", True),
            detection_backend=backend,
            detection_model_path=model_path,
            detection_model_id=model_id,
            detection_model_sha256=sha256,
            detection_input_size=input_size,
            detection_conf_threshold=_float(env, "VISTA_DETECTION_CONF_THRESHOLD", 0.30, 0.0, 1.0),
            detection_nms_iou=_float(env, "VISTA_DETECTION_NMS_IOU", 0.45, 0.0, 1.0),
            detection_max_detections=_int(env, "VISTA_DETECTION_MAX_DETECTIONS", 100, 1),
            detection_threads=_int(env, "VISTA_DETECTION_THREADS", 0, 0),
            detection_resize=_choice(env, "VISTA_DETECTION_RESIZE", "pil", DETECTION_RESIZE_MODES),
            detection_nms_mode=_choice(env, "VISTA_DETECTION_NMS_MODE", "class_aware", DETECTION_NMS_MODES),
        )