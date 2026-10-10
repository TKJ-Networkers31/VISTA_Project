"""Detection contract, normalization, geometry and configuration. No model, no network."""
import math

import numpy as np
import pytest
from pydantic import ValidationError

from core.config import ConfigError, Settings
from core.contracts import DETECTION_SCHEMA_VERSION, Detection, DetectionResponse, EngineInfo, ErrorInfo, OCRResponse
from core.detection import geometry as g
from core.detection.coco_labels import COCO_CLASSES
from core.detection.normalize import normalize_detections
from core.providers import RawDetection, RawDetectionResult


def det(**kw):
    base = dict(class_id=0, label="person", confidence=0.5, bbox2d=[1.0, 2.0, 30.0, 40.0])
    base.update(kw)
    return Detection(**base)


# ---- 1/2/3: contract validation -------------------------------------------------------------
def test_valid_detection():
    d = det()
    assert d.bbox2d == [1.0, 2.0, 30.0, 40.0] and d.confidence == 0.5


@pytest.mark.parametrize("box", [
    [1, 2, 3], [1, 2, 3, 4, 5], [0, 0, math.nan, 5], [0, 0, math.inf, 5], [-1, 0, 5, 5], [0, -0.1, 5, 5],
    [10, 0, 5, 5], [0, 10, 5, 5], [5, 5, 5, 9], [5, 5, 9, 5],
])
def test_invalid_boxes_rejected(box):
    with pytest.raises(ValidationError):
        det(bbox2d=box)


@pytest.mark.parametrize("conf", [-0.01, 1.01, math.nan, math.inf, -math.inf])
def test_invalid_confidence_rejected(conf):
    with pytest.raises(ValidationError):
        det(confidence=conf)


@pytest.mark.parametrize("conf", [0.0, 1.0])
def test_confidence_bounds_inclusive(conf):
    assert det(confidence=conf).confidence == conf


def test_negative_class_id_and_empty_label_rejected():
    with pytest.raises(ValidationError):
        det(class_id=-1)
    with pytest.raises(ValidationError):
        det(label="")


def _ok(**kw):
    base = dict(request_id="r", status="succeeded", image_width=100, image_height=50)
    base.update(kw)
    return DetectionResponse(**base)


# ---- 4: empty detections ------------------------------------------------------------------------
def test_empty_detections_are_a_valid_success():
    r = _ok()
    assert r.detections == [] and r.coordinate_space == "image_pixels" and r.bbox_format == "xyxy"
    assert r.schema_version == DETECTION_SCHEMA_VERSION


def test_response_requires_image_size_on_success():
    with pytest.raises(ValidationError):
        DetectionResponse(request_id="r", status="succeeded")


def test_response_rejects_out_of_image_detection():
    with pytest.raises(ValidationError):
        _ok(detections=[det(bbox2d=[0, 0, 101, 10])])
    with pytest.raises(ValidationError):
        _ok(detections=[det(bbox2d=[0, 0, 10, 51])])
    assert _ok(detections=[det(bbox2d=[0, 0, 100, 50])]).detections  # touching the border is inside


def test_failed_response_needs_error_and_no_detections():
    err = ErrorInfo(category="invalid_input", code="X", message="m")
    assert DetectionResponse(request_id="r", status="failed", error=err).detections == []
    with pytest.raises(ValidationError):
        DetectionResponse(request_id="r", status="failed")
    with pytest.raises(ValidationError):
        DetectionResponse(request_id="r", status="failed", error=err, detections=[det()])
    with pytest.raises(ValidationError):
        _ok(error=err)


def test_detection_shape_is_stable():
    """Fails if the response shape changes silently. A change needs an ADR and a schema_version bump."""
    assert set(DetectionResponse.model_fields) == {
        "schema_version", "request_id", "status", "filename", "image_width", "image_height", "coordinate_space",
        "bbox_format", "detections", "processing_time_ms", "engine", "model", "parameters", "warnings", "error"}
    assert set(Detection.model_fields) == {"class_id", "label", "confidence", "bbox2d"}


def test_ocr_contract_untouched():
    assert OCRResponse(request_id="x", status="failed").schema_version == "0.2-ocr-mvp"
    assert EngineInfo(id="a").locality == "local"


# ---- 5: coordinate conversion + normalization ------------------------------------------------
def raw(*items):
    return RawDetectionResult(detections=[RawDetection(*i) for i in items])


def test_normalize_clips_sorts_and_caps():
    dets, warnings = normalize_detections(raw(
        (0, 0.4, [-5.0, -5.0, 20.0, 20.0], "person"),
        (1, 0.9, [10.0, 10.0, 500.0, 500.0], "bicycle"),
        (2, 0.7, [30.0, 30.0, 60.0, 45.0], "car"),
    ), 100, 50, max_detections=2)
    assert [d.label for d in dets] == ["bicycle", "car"]  # sorted by confidence, then capped
    assert dets[0].bbox2d == [10.0, 10.0, 100.0, 50.0]  # clipped to the image
    assert warnings == []


def test_normalize_drops_and_counts_invalid_entries():
    dets, warnings = normalize_detections(raw(
        (0, math.nan, [1, 1, 5, 5], "person"),
        (0, 0.5, [1, 1, math.inf, 5], "person"),
        (0, 1.5, [1, 1, 5, 5], "person"),
        (0, 0.5, [5, 5, 1, 1], "person"),          # inverted
        (0, 0.5, [200, 200, 300, 300], "person"),  # fully outside a 100x50 image
        (0, 0.5, [1, 1, 5, 5], None),              # unlabeled
        (0, 0.5, [1, 1, 5], "person"),             # wrong arity
        (-3, 0.5, [1, 1, 5, 5], "person"),         # bad class id
        (0, 0.5, [1, 1, 5, 5], "person"),          # the one good entry
    ), 100, 50, max_detections=10)
    assert len(dets) == 1
    assert warnings and warnings[0].startswith("8 backend detection(s)")


def test_normalize_empty():
    assert normalize_detections(RawDetectionResult(), 10, 10, 5) == ([], [])


def test_letterbox_maps_boxes_back_to_original_pixels():
    from PIL import Image

    img = Image.new("RGB", (800, 400), (255, 0, 0))  # wide image: padded at the bottom
    blob, ratio = g.letterbox_image(img, 416)
    assert blob.shape == (1, 3, 416, 416) and blob.dtype == np.float32
    assert ratio == pytest.approx(416 / 800)
    assert blob[0, 2, 0, 0] == 255 and blob[0, 0, 0, 0] == 0          # BGR order: red lands in channel 2
    assert blob[0, 0, 415, 0] == g.PAD_VALUE                          # padding is 114 at the bottom
    # a box at network (104, 52)-(208, 104) is original (200, 100)-(400, 200)
    scaled = np.array([[104.0, 52.0, 208.0, 104.0]]) / ratio
    assert scaled.tolist() == [[200.0, 100.0, 400.0, 200.0]]


def test_letterbox_tall_image_pads_right():
    from PIL import Image

    blob, ratio = g.letterbox_image(Image.new("RGB", (200, 400), (0, 255, 0)), 416)
    assert ratio == pytest.approx(1.04) and blob[0, 1, 0, 0] == 255 and blob[0, 1, 0, 415] == g.PAD_VALUE


def test_letterbox_rejects_bad_sizes():
    with pytest.raises(ValueError):
        g.letterbox_size(0, 10, 416)


def _reference_decode(raw, size):
    """Deliberately naive loop version of the YOLOX head decode, to cross-check the vectorized one."""
    out = raw.copy()
    row = 0
    for stride in (8, 16, 32):
        n = size // stride
        for gy in range(n):
            for gx in range(n):
                out[row, 0] = (raw[row, 0] + gx) * stride
                out[row, 1] = (raw[row, 1] + gy) * stride
                out[row, 2] = math.exp(raw[row, 2]) * stride
                out[row, 3] = math.exp(raw[row, 3]) * stride
                row += 1
    return out


def test_decode_matches_reference_loop():
    size = 64
    rng = np.random.default_rng(0)
    raw_out = rng.normal(0, 1, (g.expected_anchor_count(size), 85)).astype(np.float32)
    np.testing.assert_allclose(g.decode_yolox(raw_out, size), _reference_decode(raw_out, size), rtol=1e-5, atol=1e-4)


def test_decode_rejects_wrong_anchor_count():
    with pytest.raises(ValueError):
        g.decode_yolox(np.zeros((10, 85), np.float32), 64)


def test_decode_does_not_mutate_input():
    size = 32
    raw_out = np.ones((g.expected_anchor_count(size), 85), np.float32)
    before = raw_out.copy()
    g.decode_yolox(raw_out, size)
    np.testing.assert_array_equal(raw_out, before)


def test_nms_suppresses_overlap_and_keeps_best():
    boxes = np.array([[0, 0, 10, 10], [1, 1, 11, 11], [50, 50, 60, 60]], float)
    keep = g.nms(boxes, np.array([0.5, 0.9, 0.7]), 0.45)
    assert keep.tolist() == [1, 2]
    assert g.nms(np.empty((0, 4)), np.empty((0,)), 0.5).size == 0


def test_class_aware_nms_keeps_overlapping_boxes_of_different_classes():
    boxes = np.array([[0, 0, 10, 10], [0, 0, 10, 10]], float)
    assert sorted(g.class_aware_nms(boxes, np.array([0.9, 0.8]), np.array([0, 1]), 0.45).tolist()) == [0, 1]
    assert g.class_aware_nms(boxes, np.array([0.9, 0.8]), np.array([3, 3]), 0.45).tolist() == [0]


def _synthetic_raw(size, cx_cell, cy_cell, stride_idx, cls, obj):
    """One strong anchor at a chosen cell/stride; everything else silent. Returns (raw, expected_xyxy_network)."""
    strides = (8, 16, 32)
    raw_out = np.zeros((g.expected_anchor_count(size), 85), np.float32)
    raw_out[:, 4] = -0.0  # objectness 0 everywhere (the model emits probabilities; 0 means "nothing")
    start = sum((size // s) ** 2 for s in strides[:stride_idx])
    n = size // strides[stride_idx]
    row = start + cy_cell * n + cx_cell
    raw_out[row, 0:2] = 0.5
    raw_out[row, 2:4] = math.log(4)  # w = h = 4 * stride
    raw_out[row, 4] = obj
    raw_out[row, 5 + cls] = 1.0
    s = strides[stride_idx]
    cx, cy, half = (cx_cell + 0.5) * s, (cy_cell + 0.5) * s, 2 * s
    return raw_out, [cx - half, cy - half, cx + half, cy + half]


def test_postprocess_end_to_end_and_ratio():
    size = 64
    raw_out, expect = _synthetic_raw(size, 4, 3, 0, cls=7, obj=0.8)
    boxes, scores, ids = g.postprocess_yolox(raw_out, size, 0.5, conf_threshold=0.3, nms_iou=0.45, max_detections=10)
    assert ids.tolist() == [7] and scores.tolist() == pytest.approx([0.8])
    np.testing.assert_allclose(boxes[0], np.clip(expect, 0, size) / 0.5, rtol=1e-6)


def test_postprocess_threshold_cap_and_nonfinite():
    size = 64
    raw_out, _ = _synthetic_raw(size, 4, 3, 0, cls=1, obj=0.25)
    assert g.postprocess_yolox(raw_out, size, 1.0, 0.3, 0.45, 10)[0].shape == (0, 4)  # below threshold
    raw_out[5, 0] = np.nan
    raw_out[6, 4] = np.inf
    boxes, scores, _ = g.postprocess_yolox(raw_out, size, 1.0, 0.1, 0.45, 10)
    assert np.isfinite(boxes).all() and np.isfinite(scores).all()
    with pytest.raises(ValueError):
        g.postprocess_yolox(raw_out, size, 0.0, 0.1, 0.45, 10)


def test_labels_are_the_80_coco_classes():
    assert len(COCO_CLASSES) == 80 and COCO_CLASSES[0] == "person" and COCO_CLASSES[79] == "toothbrush"
    assert len(set(COCO_CLASSES)) == 80


# ---- 13: configuration -----------------------------------------------------------------------------
def test_detection_defaults_are_cpu_safe():
    s = Settings.from_env({})
    assert (s.detection_enabled, s.detection_backend, s.detection_input_size) == (True, "yolox-onnx", 416)
    assert s.detection_conf_threshold == 0.30 and s.detection_max_detections == 100
    assert s.max_resident_models == 1 and s.detection_model_sha256 == ""


def test_detection_env_parsing():
    s = Settings.from_env({"VISTA_DETECTION_ENABLED": "false", "VISTA_DETECTION_CONF_THRESHOLD": "0.5",
                           "VISTA_DETECTION_MAX_DETECTIONS": "7", "VISTA_DETECTION_INPUT_SIZE": "640",
                           "VISTA_MAX_RESIDENT_MODELS": "2", "VISTA_DETECTION_MODEL_SHA256": "A" * 64})
    assert (s.detection_enabled, s.detection_conf_threshold, s.detection_max_detections) == (False, 0.5, 7)
    assert (s.detection_input_size, s.max_resident_models, s.detection_model_sha256) == (640, 2, "a" * 64)


@pytest.mark.parametrize("name,value", [
    ("VISTA_DETECTION_ENABLED", "maybe"), ("VISTA_DETECTION_BACKEND", "nope"),
    ("VISTA_DETECTION_CONF_THRESHOLD", "1.5"), ("VISTA_DETECTION_CONF_THRESHOLD", "nan"),
    ("VISTA_DETECTION_CONF_THRESHOLD", "abc"), ("VISTA_DETECTION_NMS_IOU", "-0.1"),
    ("VISTA_DETECTION_MAX_DETECTIONS", "0"), ("VISTA_DETECTION_INPUT_SIZE", "100"),
    ("VISTA_DETECTION_INPUT_SIZE", "4096"), ("VISTA_DETECTION_MODEL_SHA256", "xyz"),
    ("VISTA_DETECTION_MODEL_ID", "x" * 65), ("VISTA_MAX_RESIDENT_MODELS", "0"),
    ("VISTA_MODEL_ACQUIRE_TIMEOUT_SECONDS", "0"), ("VISTA_DETECTION_THREADS", "-1"),
])
def test_invalid_detection_config_names_variable_not_value(name, value):
    with pytest.raises(ConfigError) as e:
        Settings.from_env({name: value})
    assert name in str(e.value)
    if len(value) > 3:
        assert value not in str(e.value)
