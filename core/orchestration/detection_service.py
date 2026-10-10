"""Detection orchestration: bounded admission, lazy model load via the shared ModelManager, timeout, error envelope.

Mirrors OCRService on purpose (same admission, timeout and cancellation semantics) and shares model residency with it
through `ModelManager`. The detection model is loaded once and reused; it is never loaded per request.
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from typing import Optional

from core.config import MIME_TO_FORMAT, Settings
from core.contracts import DetectionParameters, DetectionResponse, ErrorInfo, VistaError
from core.detection.normalize import normalize_detections
from core.orchestration.model_manager import ModelManager
from core.providers import DetectionProvider
from core.vision.validation import ImageLimits, decode_image

log = logging.getLogger("vista.detection")


class DetectionService:
    def __init__(self, provider: DetectionProvider, settings: Settings, manager: Optional[ModelManager] = None) -> None:
        self.provider = provider
        self.settings = settings
        self.manager = manager
        self.limits = ImageLimits(
            max_bytes=settings.max_upload_bytes,
            max_side=settings.max_image_side,
            max_pixels=settings.max_image_pixels,
            allowed_formats=frozenset(MIME_TO_FORMAT[m] for m in settings.allowed_mime),
            allowed_mime=frozenset(settings.allowed_mime),
        )
        self.capacity = settings.worker_concurrency + settings.queue_max_size
        self._executor = ThreadPoolExecutor(max_workers=settings.worker_concurrency, thread_name_prefix="detect")
        self._lock = threading.Lock()
        self._load_lock = threading.Lock()
        self._inflight = 0
        self._closed = False
        self._active: set = set()
        self._last_load_failed = False
        if manager is not None:
            manager.register("detection", load=self._load_provider, is_loaded=provider.is_loaded,
                             unload=getattr(provider, "unload", None))

    # -- admission (bounded queue) --
    @property
    def inflight(self) -> int:
        return self._inflight

    def _reserve(self, cancel: threading.Event) -> None:
        with self._lock:
            if self._closed:
                raise VistaError("unavailable", "SERVER_SHUTTING_DOWN", "The server is shutting down.", retryable=True)
            if self._inflight >= self.capacity:
                raise VistaError("resource_limit", "QUEUE_FULL", "The server is busy. Try again shortly.",
                                 retryable=True, details={"capacity": self.capacity})
            self._inflight += 1
            self._active.add(cancel)

    def _release(self, cancel: threading.Event) -> None:
        with self._lock:
            self._inflight -= 1
            self._active.discard(cancel)

    def shutdown(self) -> None:
        """Stop admitting work and signal admitted tasks. A task already inside the model finishes that call."""
        with self._lock:
            self._closed = True
            events = list(self._active)
        for ev in events:
            ev.set()
        self._executor.shutdown(wait=False)

    # -- backend --
    def _check_available(self) -> None:
        if not self.settings.detection_enabled:
            raise VistaError("unavailable", "DETECTION_DISABLED", "Object detection is disabled by configuration.")
        ok, reason = self.provider.is_available()
        if not ok:
            raise VistaError("unavailable", "DETECTOR_UNAVAILABLE", reason or "The detection backend is not available.")

    def _load_provider(self) -> None:
        try:
            self.provider.load()
        except Exception as exc:  # backend text may contain paths; log type only
            self._last_load_failed = True
            log.error("detector load failed: %s", type(exc).__name__)
            raise VistaError("unavailable", "DETECTOR_LOAD_FAILED",
                             "The detection model could not be loaded. Check the server log.") from None
        self._last_load_failed = False

    def _ensure_loaded(self) -> None:
        with self._load_lock:
            if not self.provider.is_loaded():
                self._load_provider()

    def _model_use(self, cancel: threading.Event):
        return self.manager.use("detection", cancel) if self.manager is not None else nullcontext()

    def _parameters(self, confidence: Optional[float], max_detections: Optional[int]) -> DetectionParameters:
        s = self.settings
        # A request may only be stricter than the configured cap, never larger.
        cap = s.detection_max_detections if max_detections is None else min(max_detections, s.detection_max_detections)
        return DetectionParameters(
            confidence_threshold=s.detection_conf_threshold if confidence is None else confidence,
            nms_iou_threshold=s.detection_nms_iou, max_detections=cap, input_size=s.detection_input_size)

    def capabilities(self) -> dict:
        s = self.settings
        if not s.detection_enabled:
            status, reason = "disabled", "Detection is disabled (VISTA_DETECTION_ENABLED=false)."
        else:
            ok, reason = self.provider.is_available()
            status = "available" if ok else "unavailable"
            if ok and self._last_load_failed:
                status = "unavailable"
                reason = "The last model load failed; the next request retries. See the server log."
        return {
            "detection": {
                "implemented": True,
                "status": status,
                "reason": reason,
                "engine": self.provider.info().model_dump(),
                "model": self.provider.model_info().model_dump(),
                "model_loaded": bool(self.provider.is_loaded()),
                "parameters": self._parameters(None, None).model_dump(),
            },
            "limits": {
                "max_upload_bytes": self.limits.max_bytes,
                "max_image_side": self.limits.max_side,
                "max_image_pixels": self.limits.max_pixels,
                "allowed_mime": sorted(self.limits.allowed_mime),
                "task_timeout_seconds": s.task_timeout_seconds,
            },
            "queue": {"inflight": self._inflight, "capacity": self.capacity},
        }

    # -- pipeline (runs in a worker thread) --
    def _pipeline(self, data: bytes, mime: Optional[str], cancel: threading.Event,
                  params: DetectionParameters, out: dict) -> None:
        t0 = time.perf_counter()
        try:
            if cancel.is_set():
                raise VistaError("cancelled", "CANCELLED", "The task was cancelled.")
            dec = decode_image(data, mime, self.limits)
            out.update(width=dec.width, height=dec.height, warnings=list(dec.warnings))
            if cancel.is_set():
                raise VistaError("cancelled", "CANCELLED", "The task was cancelled.")
            self._check_available()
            if self.manager is None:
                self._ensure_loaded()
            if cancel.is_set():
                raise VistaError("cancelled", "CANCELLED", "The task was cancelled.")
            try:
                with self._model_use(cancel):
                    raw = self.provider.detect(dec.image, params.confidence_threshold, params.nms_iou_threshold,
                                               params.max_detections)
            except VistaError:
                raise
            except Exception as exc:
                log.error("detector run failed: %s", type(exc).__name__)
                raise VistaError("provider_internal", "DETECTOR_FAILED",
                                 "The detection backend failed on this image.") from None
            detections, warnings = normalize_detections(raw, dec.width, dec.height, params.max_detections)
            out["warnings"].extend(warnings)
            if not detections:
                out["warnings"].append("No objects were detected at the configured confidence threshold.")
            out["detections"] = detections
        finally:
            out["ms"] = round((time.perf_counter() - t0) * 1000, 1)

    async def process(self, data: bytes, filename: Optional[str], mime: Optional[str], request_id: str,
                      confidence: Optional[float] = None, max_detections: Optional[int] = None) -> DetectionResponse:
        out: dict = {"warnings": []}
        params = self._parameters(confidence, max_detections)
        base = dict(request_id=request_id, filename=filename, engine=self.provider.info(),
                    model=self.provider.model_info(), parameters=params)
        cancel = threading.Event()
        try:
            self._reserve(cancel)
        except VistaError as err:
            return self._failed(base, err, out)

        def job():
            try:
                self._pipeline(data, mime, cancel, params, out)
            finally:
                self._release(cancel)  # the slot is freed only when the thread really finishes

        loop = asyncio.get_running_loop()
        try:
            fut = loop.run_in_executor(self._executor, job)
        except RuntimeError:  # executor already shut down: the job never ran
            self._release(cancel)
            return self._failed(base, VistaError("unavailable", "SERVER_SHUTTING_DOWN",
                                                 "The server is shutting down.", True), out)
        try:
            await asyncio.wait_for(asyncio.shield(fut), timeout=self.settings.task_timeout_seconds)
        except asyncio.TimeoutError:
            cancel.set()
            return self._failed(base, VistaError("timeout", "TASK_TIMEOUT",
                                                 "Detection did not finish within the configured timeout.", True,
                                                 {"timeout_seconds": self.settings.task_timeout_seconds}), out)
        except VistaError as err:
            return self._failed(base, err, out)
        except Exception as exc:
            log.error("unexpected failure: %s", type(exc).__name__)
            err = VistaError("provider_internal", "INTERNAL_ERROR", "Unexpected server error.")
            return self._failed(base, err, out)

        base["model"] = self.provider.model_info()  # re-read: the file hash is only known once the model loaded
        return DetectionResponse(status="succeeded", image_width=out.get("width"), image_height=out.get("height"),
                                 detections=out["detections"], processing_time_ms=out.get("ms"),
                                 warnings=out["warnings"], **base)

    @staticmethod
    def _failed(base: dict, err: VistaError, out: dict) -> DetectionResponse:
        status = "unavailable" if err.category == "unavailable" else "failed"
        return DetectionResponse(
            status=status, image_width=out.get("width"), image_height=out.get("height"),
            processing_time_ms=out.get("ms"), warnings=list(out.get("warnings", [])),
            error=ErrorInfo(category=err.category, code=err.code, message=err.message,
                            retryable=err.retryable, details=err.details), **base)
