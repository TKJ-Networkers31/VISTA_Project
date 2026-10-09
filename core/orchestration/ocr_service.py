"""OCR orchestration: bounded admission, lazy model load, timeout, cooperative cancel, error envelope."""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from PIL import Image

from core.config import MIME_TO_FORMAT, Settings
from core.contracts import ErrorInfo, OCRResponse, VistaError
from core.ocr.normalize import normalize, raw_to_dicts
from core.providers import OCRProvider
from core.vision.validation import ImageLimits, decode_image

log = logging.getLogger("vista.ocr")


class OCRService:
    def __init__(self, provider: OCRProvider, settings: Settings) -> None:
        self.provider = provider
        self.settings = settings
        self.limits = ImageLimits(
            max_bytes=settings.max_upload_bytes,
            max_side=settings.max_image_side,
            max_pixels=settings.max_image_pixels,
            allowed_formats=frozenset(MIME_TO_FORMAT[m] for m in settings.allowed_mime),
            allowed_mime=frozenset(settings.allowed_mime),
        )
        self.capacity = settings.worker_concurrency + settings.queue_max_size
        self._executor = ThreadPoolExecutor(max_workers=settings.worker_concurrency, thread_name_prefix="ocr")
        self._lock = threading.Lock()
        self._load_lock = threading.Lock()
        self._inflight = 0
        self._closed = False
        self._active: set = set()  # cancel events of admitted tasks

    # -- admission (bounded queue) --
    @property
    def inflight(self) -> int:
        return self._inflight

    def _reserve(self, cancel: threading.Event) -> None:
        with self._lock:
            if self._closed:
                raise VistaError("unavailable", "SERVER_SHUTTING_DOWN", "The server is shutting down.", retryable=True)
            if self._inflight >= self.capacity:
                raise VistaError("resource_limit", "QUEUE_FULL",
                                 "The server is busy. Try again shortly.", retryable=True,
                                 details={"capacity": self.capacity})
            self._inflight += 1
            self._active.add(cancel)

    def _release(self, cancel: threading.Event) -> None:
        with self._lock:
            self._inflight -= 1
            self._active.discard(cancel)

    def shutdown(self) -> None:
        """Stop admitting work and ask admitted tasks to stop at their next checkpoint.

        A task already inside the OCR engine cannot be interrupted; it finishes that call first.
        """
        with self._lock:
            self._closed = True
            events = list(self._active)
        for ev in events:
            ev.set()
        self._executor.shutdown(wait=False)

    # -- engine --
    def _ensure_loaded(self) -> None:
        ok, reason = self.provider.is_available()
        if not ok:
            raise VistaError("unavailable", "ENGINE_UNAVAILABLE", reason or "OCR engine is not available.")
        with self._load_lock:
            if self.provider.is_loaded():
                return
            try:
                self.provider.load()
            except Exception as exc:  # engine text may contain paths; log type only
                log.error("engine load failed: %s", type(exc).__name__)
                raise VistaError("unavailable", "ENGINE_LOAD_FAILED",
                                 "The OCR model could not be loaded. Check the server log.") from None

    def capabilities(self) -> dict:
        ok, reason = self.provider.is_available()
        return {
            "ocr": {
                "status": "available" if ok else "unavailable",
                "reason": reason,
                "engine": self.provider.info().model_dump(),
                "model_loaded": bool(self.provider.is_loaded()),
            },
            "limits": {
                "max_upload_bytes": self.limits.max_bytes,
                "max_image_side": self.limits.max_side,
                "max_image_pixels": self.limits.max_pixels,
                "allowed_mime": sorted(self.limits.allowed_mime),
                "ocr_max_side": self.settings.ocr_max_side,
                "task_timeout_seconds": self.settings.task_timeout_seconds,
            },
            "queue": {"inflight": self._inflight, "capacity": self.capacity},
        }

    # -- pipeline (runs in a worker thread) --
    def _pipeline(self, data: bytes, mime: Optional[str], cancel: threading.Event, include_raw: bool, out: dict):
        t0 = time.perf_counter()
        try:
            if cancel.is_set():
                raise VistaError("cancelled", "CANCELLED", "The task was cancelled.")
            dec = decode_image(data, mime, self.limits)
            out.update(width=dec.width, height=dec.height, warnings=list(dec.warnings))
            if cancel.is_set():
                raise VistaError("cancelled", "CANCELLED", "The task was cancelled.")
            self._ensure_loaded()
            img, warnings = dec.image, out["warnings"]
            side = max(dec.width, dec.height)
            if side > self.settings.ocr_max_side:
                k = self.settings.ocr_max_side / side
                size = (max(1, round(dec.width * k)), max(1, round(dec.height * k)))
                img = img.resize(size, Image.LANCZOS)
                warnings.append(f"Downscaled for OCR from {dec.width}x{dec.height} to {size[0]}x{size[1]}; "
                                "coordinates are mapped back to original pixels.")
            if cancel.is_set():
                raise VistaError("cancelled", "CANCELLED", "The task was cancelled.")
            try:
                raw = self.provider.recognize(img)
            except VistaError:
                raise
            except Exception as exc:
                log.error("engine run failed: %s", type(exc).__name__)
                raise VistaError("provider_internal", "ENGINE_FAILED", "The OCR engine failed on this image.") from None
            blocks, text = normalize(raw, dec.width / img.size[0], dec.height / img.size[1], dec.width, dec.height)
            if not blocks:
                warnings.append("No text was detected in the image.")
            if any(b.bbox2d is None for b in blocks):
                warnings.append("The engine returned some text without coordinates; those blocks have no bbox2d.")
            out.update(blocks=blocks, text=text, raw=raw_to_dicts(raw) if include_raw else None)
        finally:
            out["ms"] = round((time.perf_counter() - t0) * 1000, 1)

    async def process(self, data: bytes, filename: Optional[str], mime: Optional[str],
                      request_id: str, include_raw: bool = False) -> OCRResponse:
        out: dict = {"warnings": []}
        base = dict(request_id=request_id, filename=filename, engine=self.provider.info())
        cancel = threading.Event()
        try:
            self._reserve(cancel)
        except VistaError as err:
            return self._failed(base, err, out)

        def job():
            try:
                self._pipeline(data, mime, cancel, include_raw, out)
            finally:
                self._release(cancel)  # slot is freed only when the thread really finishes

        loop = asyncio.get_running_loop()
        try:
            fut = loop.run_in_executor(self._executor, job)
        except RuntimeError:  # executor already shut down: job never ran, so free the slot here
            self._release(cancel)
            return self._failed(base, VistaError("unavailable", "SERVER_SHUTTING_DOWN",
                                                 "The server is shutting down.", True), out)
        try:
            await asyncio.wait_for(asyncio.shield(fut), timeout=self.settings.task_timeout_seconds)
        except asyncio.TimeoutError:
            cancel.set()  # cooperative: stops at the next checkpoint
            return self._failed(base, VistaError("timeout", "TASK_TIMEOUT",
                                                 "OCR did not finish within the configured timeout.", True,
                                                 {"timeout_seconds": self.settings.task_timeout_seconds}), out)
        except VistaError as err:
            return self._failed(base, err, out)
        except Exception as exc:
            log.error("unexpected failure: %s", type(exc).__name__)
            err = VistaError("provider_internal", "INTERNAL_ERROR", "Unexpected server error.")
            return self._failed(base, err, out)

        return OCRResponse(status="succeeded", image_width=out.get("width"), image_height=out.get("height"),
                           detected_text=out["text"], blocks=out["blocks"], processing_time_ms=out.get("ms"),
                           warnings=out["warnings"], raw=out.get("raw"), **base)

    @staticmethod
    def _failed(base: dict, err: VistaError, out: dict) -> OCRResponse:
        status = "unavailable" if err.category == "unavailable" else "failed"
        return OCRResponse(
            status=status, image_width=out.get("width"), image_height=out.get("height"),
            processing_time_ms=out.get("ms"), warnings=list(out.get("warnings", [])),
            error=ErrorInfo(category=err.category, code=err.code, message=err.message,
                            retryable=err.retryable, details=err.details), **base)
