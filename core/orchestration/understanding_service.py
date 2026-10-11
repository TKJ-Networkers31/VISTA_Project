"""Image-understanding orchestration: policy decision, bounded admission, JPEG re-encode, external call, error envelope.

Order of work (nothing is sent anywhere before step 3 passes):
  1. validate the question; 2. core.routing.decide (mode, consent, external config); 3. reserve a queue slot;
  4. decode + validate the image with the same limits as OCR/detection; 5. re-encode a small JPEG; 6. provider call.
A rejected request (steps 1-2) never decodes the image and never touches the provider. There is no silent fallback:
the response `route` says what happened, including `external_transmission`.
No local provider supports this capability; OCR and detection are never used as a substitute for it.
"""
from __future__ import annotations

import asyncio
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional

from core.config import MIME_TO_FORMAT, Settings
from core.contracts import ErrorInfo, UnderstandingResponse, UnderstandingRoute, VistaError
from core.routing import ExternalConfig, PolicyDecision, PolicyError, decide
from core.vision.encode import prepare_jpeg
from core.vision.validation import ImageLimits, decode_image

log = logging.getLogger("vista.understanding")

CAPABILITY = "image_understanding"
DEFAULT_QUESTION = "Describe this image."
QUESTION_MAX_CHARS = 1000
LOCAL_CAPABILITIES = frozenset({"ocr", "detection"})  # image_understanding is deliberately NOT local
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")  # newlines and tabs are allowed in a question
_POLICY_CATEGORY = {"CONSENT_REQUIRED": "invalid_input", "INVALID_MODE": "invalid_input",
                    "EXTERNAL_DISABLED": "unavailable", "EXTERNAL_NOT_CONFIGURED": "unavailable",
                    "CAPABILITY_UNSUPPORTED": "not_implemented"}


def clean_question(question: Optional[str]) -> str:
    if question is None or question.strip() == "":
        return DEFAULT_QUESTION
    text = question.strip()
    if len(text) > QUESTION_MAX_CHARS or _CONTROL.search(text):
        raise VistaError("invalid_input", "INVALID_PARAMETER",
                         f"question must be at most {QUESTION_MAX_CHARS} printable characters.")
    return text


class UnderstandingService:
    def __init__(self, adapter: Any, settings: Settings) -> None:
        self.adapter = adapter  # NimAdapter or a test double: supports, is_configured(), describe(), ask()
        self.settings = settings
        self.limits = ImageLimits(
            max_bytes=settings.max_upload_bytes,
            max_side=settings.max_image_side,
            max_pixels=settings.max_image_pixels,
            allowed_formats=frozenset(MIME_TO_FORMAT[m] for m in settings.allowed_mime),
            allowed_mime=frozenset(settings.allowed_mime),
        )
        self.capacity = settings.worker_concurrency + settings.queue_max_size
        self._executor = ThreadPoolExecutor(max_workers=settings.worker_concurrency, thread_name_prefix="understand")
        self._lock = threading.Lock()
        self._inflight = 0
        self._closed = False
        self._active: set = set()

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
        with self._lock:
            self._closed = True
            events = list(self._active)
        for ev in events:
            ev.set()
        self._executor.shutdown(wait=False)

    # -- policy --
    def _external_config(self) -> ExternalConfig:
        supports = frozenset(getattr(self.adapter, "supports", ()))
        return ExternalConfig(enabled=self.settings.external_enabled,
                              has_credentials=bool(self.adapter.is_configured()),
                              capabilities=supports, external_capabilities=frozenset({CAPABILITY}),
                              local_capabilities=LOCAL_CAPABILITIES)

    def _decide(self, mode: str, consent: bool) -> PolicyDecision:
        try:
            decision = decide(mode, CAPABILITY, consent, self._external_config())
        except PolicyError as err:
            raise VistaError(_POLICY_CATEGORY.get(err.code, "invalid_input"), err.code, err.message) from None
        if decision.target != "external":  # cannot happen today; never answer from a different capability
            raise VistaError("not_implemented", "CAPABILITY_UNSUPPORTED",
                             "No local provider supports image understanding.")
        return decision

    def capabilities(self) -> dict:
        s = self.settings
        configured = bool(self.adapter.is_configured())
        if not s.external_enabled:
            status, reason = "disabled", "External providers are disabled (VISTA_EXTERNAL_ENABLED=false)."
        elif not configured:
            status, reason = "unavailable", "No NVIDIA NIM API key is configured (VISTA_NIM_API_KEY)."
        else:
            status, reason = "available", None
        return {
            "understanding": {
                "implemented": True,
                "status": status,
                "reason": reason,
                "locality": "external",
                "requires_consent": True,
                "supports": [CAPABILITY],
                "provides_bounding_boxes": False,
                "provider": self.adapter.describe(),
                "policy_default": s.policy_default,
                "modes": ["local_only", "hybrid", "external_fallback"],
                "note": "No local provider exists for this capability: local_only always rejects it.",
            },
            "limits": {
                "max_upload_bytes": self.limits.max_bytes,
                "question_max_chars": QUESTION_MAX_CHARS,
                "image_sent_max_side": s.understanding_max_side,
                "image_sent_max_bytes": s.nim_max_image_bytes,
                "task_timeout_seconds": s.task_timeout_seconds,
            },
            "queue": {"inflight": self._inflight, "capacity": self.capacity},
        }

    # -- pipeline (runs in a worker thread) --
    def _pipeline(self, data: bytes, mime: Optional[str], cancel: threading.Event, question: str, out: dict) -> None:
        t0 = time.perf_counter()
        try:
            if cancel.is_set():
                raise VistaError("cancelled", "CANCELLED", "The task was cancelled.")
            dec = decode_image(data, mime, self.limits)
            out.update(width=dec.width, height=dec.height, warnings=list(dec.warnings))
            if cancel.is_set():
                raise VistaError("cancelled", "CANCELLED", "The task was cancelled.")
            jpeg, note = prepare_jpeg(dec.image, self.settings.understanding_max_side,
                                      self.settings.nim_max_image_bytes)
            out["warnings"].append(note)
            if cancel.is_set():
                raise VistaError("cancelled", "CANCELLED", "The task was cancelled.")

            def mark_sent() -> None:
                out["sent"] = True

            out["answer"] = self.adapter.ask(jpeg, question, on_send=mark_sent)
        except VistaError:
            raise
        except Exception as exc:  # message may hold paths/keys: log the type only
            log.error("understanding failed: %s", type(exc).__name__)
            raise VistaError("provider_internal", "INTERNAL_ERROR", "Unexpected server error.") from None
        finally:
            out["ms"] = round((time.perf_counter() - t0) * 1000, 1)

    def _route(self, mode: str, target: str, reason: str, sent: bool) -> UnderstandingRoute:
        info: Dict[str, Any] = self.adapter.describe() if target == "external" else {}
        return UnderstandingRoute(mode=mode, target=target, reason=reason, provider=info.get("provider"),
                                  model=info.get("model"), external_transmission=sent)

    async def process(self, data: bytes, filename: Optional[str], mime: Optional[str], request_id: str,
                      question: Optional[str] = None, mode: Optional[str] = None,
                      consent: bool = False) -> UnderstandingResponse:
        out: dict = {"warnings": [], "sent": False}
        base: Dict[str, Any] = dict(request_id=request_id, filename=filename)
        mode_used = (mode or self.settings.policy_default).strip().lower()[:32]
        try:
            text = clean_question(question)
            base["question"] = text
            decision = self._decide(mode_used, bool(consent))
        except VistaError as err:  # rejected before anything was decoded or sent
            return self._failed(base, err, out, self._route(mode_used, "none", err.code, False))
        route_ok = (mode_used, "external", decision.reason)

        cancel = threading.Event()
        try:
            self._reserve(cancel)
        except VistaError as err:
            return self._failed(base, err, out, self._route(mode_used, "none", err.code, False))

        def job() -> None:
            try:
                self._pipeline(data, mime, cancel, text, out)
            finally:
                self._release(cancel)  # the slot is freed only when the thread really finishes

        loop = asyncio.get_running_loop()
        try:
            fut = loop.run_in_executor(self._executor, job)
        except RuntimeError:  # executor already shut down: the job never ran
            self._release(cancel)
            err = VistaError("unavailable", "SERVER_SHUTTING_DOWN", "The server is shutting down.", True)
            return self._failed(base, err, out, self._route(mode_used, "none", err.code, False))
        try:
            await asyncio.wait_for(asyncio.shield(fut), timeout=self.settings.task_timeout_seconds)
        except asyncio.TimeoutError:
            cancel.set()
            err = VistaError("timeout", "TASK_TIMEOUT", "The request did not finish within the configured timeout.",
                             True, {"timeout_seconds": self.settings.task_timeout_seconds})
            return self._failed(base, err, out, self._route(*route_ok, out["sent"]))
        except VistaError as err:
            return self._failed(base, err, out, self._route(*route_ok, out["sent"]))
        except Exception as exc:
            log.error("unexpected failure: %s", type(exc).__name__)
            err = VistaError("provider_internal", "INTERNAL_ERROR", "Unexpected server error.")
            return self._failed(base, err, out, self._route(*route_ok, out["sent"]))

        return UnderstandingResponse(status="succeeded", image_width=out.get("width"), image_height=out.get("height"),
                                     answer=out["answer"], route=self._route(*route_ok, out["sent"]),
                                     processing_time_ms=out.get("ms"), warnings=out["warnings"], **base)

    @staticmethod
    def _failed(base: dict, err: VistaError, out: dict, route: UnderstandingRoute) -> UnderstandingResponse:
        status = "unavailable" if err.category == "unavailable" else "failed"
        return UnderstandingResponse(
            status=status, image_width=out.get("width"), image_height=out.get("height"), route=route,
            processing_time_ms=out.get("ms"), warnings=list(out.get("warnings", [])),
            error=ErrorInfo(category=err.category, code=err.code, message=err.message,
                            retryable=err.retryable, details=err.details), **base)
