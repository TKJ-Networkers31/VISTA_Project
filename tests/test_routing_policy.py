import pytest

from core.routing import ExternalConfig, PolicyError, decide, may_fallback

LOC = frozenset({"ocr", "detection"})
EXT = frozenset({"image_understanding"})


def cfg(**kw):
    base = dict(enabled=True, has_credentials=True, capabilities=EXT | {"ocr"}, external_capabilities=EXT,
                local_capabilities=LOC)
    base.update(kw)
    return ExternalConfig(**base)


@pytest.mark.parametrize("consent", [True, False])
def test_local_only_never_goes_external(consent):
    assert decide("local_only", "ocr", consent, cfg()).target == "local"
    with pytest.raises(PolicyError) as e:
        decide("local_only", "image_understanding", consent, cfg())
    assert e.value.code == "CAPABILITY_UNSUPPORTED"


def test_hybrid_routes_by_capability_and_needs_consent():
    assert decide("hybrid", "detection", False, cfg()).target == "local"
    with pytest.raises(PolicyError) as e:
        decide("hybrid", "image_understanding", False, cfg())
    assert e.value.code == "CONSENT_REQUIRED"
    assert decide("hybrid", "image_understanding", True, cfg()).target == "external"


@pytest.mark.parametrize("kw,code", [({"enabled": False}, "EXTERNAL_DISABLED"),
                                     ({"has_credentials": False}, "EXTERNAL_NOT_CONFIGURED"),
                                     ({"capabilities": frozenset()}, "CAPABILITY_UNSUPPORTED")])
def test_hybrid_external_not_ready(kw, code):
    with pytest.raises(PolicyError) as e:
        decide("hybrid", "image_understanding", True, cfg(**kw))
    assert e.value.code == code


def test_fallback_requires_consent_and_eligible_error():
    d = decide("external_fallback", "ocr", True, cfg())
    assert d.target == "local" and d.allow_fallback
    assert may_fallback(d, "unavailable") and may_fallback(d, "timeout")
    assert not may_fallback(d, "invalid_input") and not may_fallback(d, "cancelled")
    assert not decide("external_fallback", "ocr", False, cfg()).allow_fallback
    assert not decide("external_fallback", "ocr", True, cfg(enabled=False)).allow_fallback


def test_unknown_mode_rejected():
    with pytest.raises(PolicyError) as e:
        decide("auto", "ocr", True, cfg())
    assert e.value.code == "INVALID_MODE"
