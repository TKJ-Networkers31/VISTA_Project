"""HTTP layer: request/response mapping only. Calls core/orchestration."""
from __future__ import annotations

import logging
import re
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.config import Settings
from core.contracts import SCHEMA_VERSION, ErrorInfo, OCRResponse
from core.ocr import create_provider
from core.orchestration import OCRService

log = logging.getLogger("vista.api")
WEB_DIR = Path(__file__).resolve().parents[1] / "web" / "static"
FILE_FIELD = File(...)
BODY_SLACK = 64 * 1024  # multipart overhead allowed on top of max_upload_bytes

HTTP_BY_CODE = {"EMPTY_FILE": 400, "CORRUPT_IMAGE": 400, "MISSING_FILE": 400, "IMAGE_TOO_LARGE": 413,
                "IMAGE_DIMENSIONS_EXCEEDED": 413, "UNSUPPORTED_FORMAT": 415, "LENGTH_REQUIRED": 411}
HTTP_BY_CATEGORY = {"invalid_input": 400, "resource_limit": 429, "unavailable": 503, "timeout": 504,
                    "cancelled": 503, "provider_internal": 500}


def _http_status(resp: OCRResponse) -> int:
    if resp.status == "succeeded" or resp.error is None:
        return 200
    return HTTP_BY_CODE.get(resp.error.code) or HTTP_BY_CATEGORY.get(resp.error.category, 500)


def _safe_name(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    base = re.split(r"[\\/]", name)[-1]
    base = re.sub(r"[\x00-\x1f\x7f]", "", base)[:255]
    return base or None


def _error_response(code: str, category: str, message: str, status: int, **details) -> JSONResponse:
    body = OCRResponse(request_id="req_" + uuid.uuid4().hex[:12], status="failed",
                       error=ErrorInfo(category=category, code=code, message=message, details=details))
    return JSONResponse(body.model_dump(), status_code=status)


def create_app(settings: Optional[Settings] = None, provider=None) -> FastAPI:
    settings = settings or Settings.from_env()
    provider = provider or create_provider(settings.ocr_engine)
    service = OCRService(provider, settings)
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        service.shutdown()

    app = FastAPI(title="VISTA", version="0.1.0", docs_url="/docs", redoc_url=None, lifespan=lifespan)
    app.state.service = service
    app.state.settings = settings

    @app.middleware("http")
    async def limit_body(request: Request, call_next):
        if request.method == "POST" and request.url.path == "/api/v1/ocr":
            length = request.headers.get("content-length")
            if length is None or not length.isdigit():
                return _error_response("LENGTH_REQUIRED", "invalid_input", "Content-Length header is required.", 411)
            if int(length) > settings.max_upload_bytes + BODY_SLACK:
                return _error_response("IMAGE_TOO_LARGE", "invalid_input",
                                       "The request exceeds the configured size limit.", 413,
                                       limit_bytes=settings.max_upload_bytes)
        return await call_next(request)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, __: RequestValidationError):
        return _error_response("MISSING_FILE", "invalid_input", "Send one image in the multipart field 'file'.", 400)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        cat = "invalid_input" if exc.status_code < 500 else "provider_internal"
        return _error_response("HTTP_" + str(exc.status_code), cat, "Request could not be handled.", exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.error("unhandled error: %s", type(exc).__name__)
        return _error_response("INTERNAL_ERROR", "provider_internal", "Unexpected server error.", 500)

    @app.get("/health")
    async def health():
        caps = service.capabilities()
        return {"schema_version": SCHEMA_VERSION, "status": "ok", "capabilities": {"ocr": caps["ocr"]},
                "queue": caps["queue"]}

    @app.get("/api/v1/ocr/capabilities")
    async def capabilities():
        return {"schema_version": SCHEMA_VERSION, **service.capabilities()}

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

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(WEB_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
    return app


def build_default_app() -> FastAPI:  # for `uvicorn apps.api.main:build_default_app --factory`
    from core.config import load_dotenv

    load_dotenv(Path.cwd() / ".env")
    return create_app()
