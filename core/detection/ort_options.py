"""ONNX Runtime SessionOptions for the detection providers, in one place.

Defaults reproduce the previous behaviour (sequential execution, ONNX Runtime chooses threads). Which values are best
on the X270 is decided by scripts/benchmark_ort_threads.py, not assumed.
"""
from __future__ import annotations

from typing import Any

EXEC_MODES = ("sequential", "parallel")


def build_session_options(ort: Any, threads: int = 0, inter_op_threads: int = 0, exec_mode: str = "sequential") -> Any:
    if exec_mode not in EXEC_MODES:
        raise ValueError("exec_mode must be one of: " + ", ".join(EXEC_MODES))
    if threads < 0 or inter_op_threads < 0:
        raise ValueError("thread counts must be >= 0")
    options = ort.SessionOptions()
    options.log_severity_level = 3
    if threads > 0:
        options.intra_op_num_threads = threads
    if inter_op_threads > 0:
        options.inter_op_num_threads = inter_op_threads
    mode = ort.ExecutionMode.ORT_PARALLEL if exec_mode == "parallel" else ort.ExecutionMode.ORT_SEQUENTIAL
    options.execution_mode = mode
    return options
