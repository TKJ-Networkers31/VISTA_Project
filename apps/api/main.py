"""HTTP layer: request/response mapping only. Calls core/orchestration."""
from __future__ import annotations

import logging
import re
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.config import Settings
from core.contracts import (
    DETECTION_SCHEMA_VERSION,
    SCHEMA_VERSION,
    UNDERSTANDING_SCHEMA_VERSION,
    DetectionResponse,
    ErrorInfo,
    OCRResponse,
    UnderstandingResponse,
)
from core.detection import create_detection_provider
from core.ocr import create_provider
from core.orchestration import DetectionService, ModelManager, OCRService, UnderstandingService
from core.providers.nim import NimAdapter, NimConfig
from core.routing import CallBudget

log = logging.getLogger("vista.api")
WEB_DIR = Path(__file__).resolve().parents[1] / "web" / "static"
FILE_FIELD = File(...)
BODY_SLACK = 64 * 1024  # multipart overhead allowed on top of max_upload_bytes
OCR_PATH = "/api/v1/ocr"
DETECTION_PATH = "/api/v1/detection"
UNDERSTANDING_PATH = "/api/v1/understanding"
UPLOAD_PATHS = (OCR_PATH, DETECTION_PATH, UNDERSTANDING_PATH)
ERROR_MODELS = {DETECTION_PATH: DetectionResponse, UNDERSTANDING_PATH: UnderstandingResponse}

HTTP_BY_CODE = {"EMPTY_FILE": 400, "CORRUPT_IMAGE": 400, "MISSING_FILE": 400, "IMAGE_TOO_LARGE": 413,
                "IMAGE_DIMENSIONS_EXCEEDED": 413, "UNSUPPORTED_FORMAT": 415, "LENGTH_REQUIRED": 411,
                "CONSENT_REQUIRED": 403, "IMAGE_TOO_LARGE_FOR_PROVIDER": 413,
                "NIM_AUTH_FAILED": 502, "NIM_BAD_REQUEST": 502, "NIM_MALFORMED": 502, "NIM_EMPTY": 502,
                "NIM_SERVER_ERROR": 502}
HTTP_BY_CATEGORY = {"invalid_input": 400, "resource_limit": 429, "unavailable": 503, "timeout": 504,
                    "cancelled": 503, "provider_internal": 500, "not_implemented": 501}


def _http_status(resp) -> int:  # OCR, detection or understanding response: all expose status and error
    if resp.status == "succeeded" or resp.error is None:
        return 200
    return HTTP_BY_CODE.get(resp.error.code) or HTTP_BY_CATEGORY.get(resp.error.category, 500)


def _safe_name(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    base = re.split(r"[\\/]", name)[-1]
    base = re.sub(r"[\x00-\x1f\x7f]", "", base)[:255]
    return base or None


def _error_response(code: str, category: str, message: str, status: int, _path: Optional[str] = None,
                    **details) -> JSONResponse:
    """Error envelope in the shape of the route that failed (detection/understanding routes get their own contract)."""
    model = ERROR_MODELS.get(_path, OCRResponse)
    body = model(request_id="req_" + uuid.uuid4().hex[:12], status="failed",
                 error=ErrorInfo(category=category, code=code, message=message, details=details))
    return JSONResponse(body.model_dump(), status_code=status)


def create_app(settings: Optional[Settings] = None, provider=None, detection_provider=None,
               understanding_adapter=None) -> FastAPI:
    settings = settings or Settings.from_env()
    provider = provider or create_provider(settings.ocr_engine)
    detection_provider = detection_provider or create_detection_provider(settings)
    manager = ModelManager(settings.max_resident_models, settings.model_acquire_timeout_seconds)
    service = OCRService(provider, settings, manager)
    detection_service = DetectionService(detection_provider, settings, manager)
    if understanding_adapter is None:
        understanding_adapter = NimAdapter(
            NimConfig(api_key=settings.nim_api_key, base_url=settings.nim_base_url, model=settings.nim_model,
                      timeout_seconds=settings.external_timeout_seconds, max_tokens=settings.nim_max_tokens,
                      enable_thinking=settings.nim_enable_thinking, max_retries=settings.external_retry_max),
            budget=CallBudget(settings.external_daily_call_limit))
    understanding_service = UnderstandingService(understanding_adapter, settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        manager.close()
        service.shutdown()
        detection_service.shutdown()
        understanding_service.shutdown()

    app = FastAPI(title="VISTA", version="0.1.0", docs_url="/docs", redoc_url=None, lifespan=lifespan)
    app.state.service = service
    app.state.detection_service = detection_service
    app.state.understanding_service = understanding_service
    app.state.models = manager
    app.state.settings = settings

    @app.middleware("http")
    async def limit_body(request: Request, call_next):
        if request.method == "POST" and request.url.path in UPLOAD_PATHS:
            path = request.url.path
            length = request.headers.get("content-length")
            if length is None or not length.isdigit():
                return _error_response("LENGTH_REQUIRED", "invalid_input", "Content-Length header is required.", 411,
                                       path)
            if int(length) > settings.max_upload_bytes + BODY_SLACK:
                return _error_response("IMAGE_TOO_LARGE", "invalid_input",
                                       "The request exceeds the configured size limit.", 413, path,
                                       limit_bytes=settings.max_upload_bytes)
        return await call_next(request)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        path = request.url.path
        if path in (DETECTION_PATH, UNDERSTANDING_PATH) and not any("file" in e.get("loc", ())
                                                                    for e in exc.errors()):
            what = "query parameter" if path == DETECTION_PATH else "form field"
            return _error_response("INVALID_PARAMETER", "invalid_input",
                                   f"A {what} is missing or out of range.", 400, path)
        return _error_response("MISSING_FILE", "invalid_input", "Send one image in the multipart field 'file'.", 400,
                               path)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        cat = "invalid_input" if exc.status_code < 500 else "provider_internal"
        return _error_response("HTTP_" + str(exc.status_code), cat, "Request could not be handled.", exc.status_code,
                               request.url.path)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        log.error("unhandled error: %s", type(exc).__name__)
        return _error_response("INTERNAL_ERROR", "provider_internal", "Unexpected server error.", 500,
                               request.url.path)

    @app.get("/health")
    async def health():
        caps = service.capabilities()
        det = detection_service.capabilities()["detection"]
        return {"schema_version": SCHEMA_VERSION, "status": "ok",
                "capabilities": {"ocr": caps["ocr"],
                                 "detection": {k: det[k] for k in ("implemented", "status", "reason", "model_loaded")}},
                "queue": caps["queue"]}

    @app.get("/api/v1/ocr/capabilities")
    async def capabilities():
        return {"schema_version": SCHEMA_VERSION, **service.capabilities()}

    @app.get("/api/v1/capabilities")
    async def all_capabilities():
        """One view of every capability: implemented? available? Detection is `available` only when usable."""
        ocr_caps = service.capabilities()["ocr"]
        return {"schema_version": SCHEMA_VERSION,
                "ocr": {"implemented": True, **ocr_caps},
                **{k: v for k, v in detection_service.capabilities().items() if k == "detection"},
                "understanding": understanding_service.capabilities()["understanding"],
                "spatial": {"implemented": False, "status": "not_implemented"},
                "models": {"max_resident": manager.max_resident, "state": manager.status()}}

    @app.get("/api/v1/detection/capabilities")
    async def detection_capabilities():
        return {"schema_version": DETECTION_SCHEMA_VERSION, **detection_service.capabilities()}

    @app.get("/api/v1/understanding/capabilities")
    async def understanding_capabilities():
        return {"schema_version": UNDERSTANDING_SCHEMA_VERSION, **understanding_service.capabilities()}

    @app.post("/api/v1/ocr", response_model=OCRResponse, response_model_exclude_none=False)
    async def ocr(file: UploadFile = FILE_FIELD, include_raw: bool = False):
        request_id = "req_" + uuid.uuid4().hex[:12]
        try:
            data = await file.read()
        finally:
            await file.close()
        resp = await service.process(data, _safe_name(file.filename), file.content_type, request_id, include_raw)
        log.info("request_id=%s status=%s code=%s bytes=%d ms=%s", request_id, resp.status,
                 resp.error.code if resp.error else "-", len(data), resp.processing_time_ms)
        return JSONResponse(resp.model_dump(), status_code=_http_status(resp))

    @app.post("/api/v1/detection", response_model=DetectionResponse, response_model_exclude_none=False)
    async def detection(file: UploadFile = FILE_FIELD,
                        confidence: Optional[float] = Query(None, ge=0.0, le=1.0, allow_inf_nan=False),
                        max_detections: Optional[int] = Query(None, ge=1),
                        prompt: Optional[str] = Query(None, max_length=200)):
        request_id = "req_" + uuid.uuid4().hex[:12]
        try:
            data = await file.read()
        finally:
            await file.close()
        resp = await detection_service.process(data, _safe_name(file.filename), file.content_type, request_id,
                                               confidence, max_detections, prompt)
        log.info("request_id=%s detection status=%s code=%s bytes=%d n=%d ms=%s", request_id, resp.status,
                 resp.error.code if resp.error else "-", len(data), len(resp.detections), resp.processing_time_ms)
        return JSONResponse(resp.model_dump(), status_code=_http_status(resp))

    @app.post("/api/v1/understanding", response_model=UnderstandingResponse, response_model_exclude_none=False)
    async def understanding(file: UploadFile = FILE_FIELD, question: Optional[str] = Form(None),
                            mode: Optional[str] = Form(None), consent_external: bool = Form(False)):
        """question/mode/consent travel in the multipart BODY, not the URL: the access log never holds them."""
        request_id = "req_" + uuid.uuid4().hex[:12]
        try:
            data = await file.read()
        finally:
            await file.close()
        resp = await understanding_service.process(data, _safe_name(file.filename), file.content_type, request_id,
                                                   question, mode, consent_external)
        route = resp.route
        log.info("request_id=%s understanding status=%s code=%s mode=%s target=%s sent=%s bytes=%d ms=%s",
                 request_id, resp.status, resp.error.code if resp.error else "-", route.mode if route else "-",
                 route.target if route else "-", route.external_transmission if route else "-", len(data),
                 resp.processing_time_ms)
        return JSONResponse(resp.model_dump(), status_code=_http_status(resp))

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(WEB_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
    return app


def build_default_app() -> FastAPI:  # for `uvicorn apps.api.main:build_default_app --factory`
    from core.config import load_dotenv

    load_dotenv(Path.cwd() / ".env")
    return create_app()
