"""SessionOptions helper and benchmark config parsing. Fake ort object: no model, no onnxruntime needed."""
import types

import pytest

from core.detection.ort_options import build_session_options
from scripts.benchmark_ort_threads import parse_config, percentile


class _Opts:
    pass


FAKE_ORT = types.SimpleNamespace(
    SessionOptions=_Opts,
    ExecutionMode=types.SimpleNamespace(ORT_SEQUENTIAL="seq", ORT_PARALLEL="par"))


def test_defaults_keep_previous_behaviour():
    o = build_session_options(FAKE_ORT)
    assert o.log_severity_level == 3 and o.execution_mode == "seq"
    assert not hasattr(o, "intra_op_num_threads") and not hasattr(o, "inter_op_num_threads")


def test_explicit_values_are_applied():
    o = build_session_options(FAKE_ORT, 2, 3, "parallel")
    assert (o.intra_op_num_threads, o.inter_op_num_threads, o.execution_mode) == (2, 3, "par")


@pytest.mark.parametrize("kw", [{"exec_mode": "weird"}, {"threads": -1}, {"inter_op_threads": -1}])
def test_invalid_values_rejected(kw):
    with pytest.raises(ValueError):
        build_session_options(FAKE_ORT, **kw)


def test_parse_config_and_percentile():
    assert parse_config("2:seq") == (2, "sequential", 0) and parse_config("4:par:2") == (4, "parallel", 2)
    for bad in ("2", "x:seq", "2:fast", "-1:seq", "1:2:3:4"):
        with pytest.raises(SystemExit):
            parse_config(bad)
    assert percentile([1, 2, 3, 4], 95) == 4 and percentile([], 95) is None
