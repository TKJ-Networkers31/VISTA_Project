import pytest
from pydantic import ValidationError

from core.contracts import (
    UNDERSTANDING_SCHEMA_VERSION,
    ErrorInfo,
    OCRResponse,
    UnderstandingResponse,
    UnderstandingRoute,
)


def route(**kw):
    base = dict(mode="hybrid", target="external", reason="HYBRID_EXTERNAL", provider="p", model="m",
                external_transmission=True)
    base.update(kw)
    return UnderstandingRoute(**base)


def test_valid_success():
    r = UnderstandingResponse(request_id="r", status="succeeded", answer="A cat.", route=route())
    assert r.schema_version == UNDERSTANDING_SCHEMA_VERSION == "0.4-understanding"


@pytest.mark.parametrize("kw", [{"answer": None}, {"answer": "   "}, {"route": None},
                                {"route": route(target="none", external_transmission=False)},
                                {"error": ErrorInfo(category="x", code="X", message="m")}])
def test_invalid_success(kw):
    base = dict(request_id="r", status="succeeded", answer="A cat.", route=route())
    base.update(kw)
    with pytest.raises(ValidationError):
        UnderstandingResponse(**base)


def test_failed_needs_error_and_no_answer():
    err = ErrorInfo(category="invalid_input", code="CONSENT_REQUIRED", message="m")
    ok = UnderstandingResponse(request_id="r", status="failed", error=err,
                               route=route(target="none", external_transmission=False))
    assert ok.answer is None
    with pytest.raises(ValidationError):
        UnderstandingResponse(request_id="r", status="failed")
    with pytest.raises(ValidationError):
        UnderstandingResponse(request_id="r", status="failed", error=err, answer="leak")


def test_shape_is_stable():
    """Fails if the response shape changes silently. A change needs an ADR and a schema_version bump."""
    assert set(UnderstandingResponse.model_fields) == {
        "schema_version", "request_id", "status", "filename", "image_width", "image_height", "question", "answer",
        "route", "processing_time_ms", "warnings", "error"}
    assert set(UnderstandingRoute.model_fields) == {"mode", "target", "reason", "provider", "model",
                                                    "external_transmission"}


def test_ocr_contract_untouched():
    assert OCRResponse(request_id="x", status="failed").schema_version == "0.2-ocr-mvp"
