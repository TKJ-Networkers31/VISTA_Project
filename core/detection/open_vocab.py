"""Open-vocabulary (text-prompted) detection: EXPERIMENTAL and UNSUPPORTED in this build.

No grounding model has been verified here (weights, license, ONNX export, operators, tokenizer, RAM). This provider
never returns detections and never substitutes a closed-vocabulary model.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from core.contracts import DetectionModelInfo, EngineInfo

REASON = ("Open-vocabulary detection is experimental and not supported yet: no text+image model has been "
          "exported and verified on ONNX Runtime CPU. See docs/DETECTION_PROVIDERS.md (next experiment steps).")


class OpenVocabularyProvider:
    supports_prompt = True

    def info(self) -> EngineInfo:
        return EngineInfo(id="onnxruntime", version=None, locality="local")

    def model_info(self) -> DetectionModelInfo:
        return DetectionModelInfo(id="open-vocabulary-unsupported", family="grounding")

    def describe(self) -> Dict[str, Any]:
        return {"family": "grounding", "supported": False, "experimental": True, "classes": {"source": "text prompt"},
                "runtime": "onnxruntime CPUExecutionProvider (not verified)",
                "limitations": [REASON], "license": "not evaluated"}

    def is_available(self) -> Tuple[bool, Optional[str]]:
        return False, REASON

    def is_loaded(self) -> bool:
        return False

    def load(self) -> None:
        raise RuntimeError("unsupported")

    def unload(self) -> None:
        return None

    def detect(self, *args: Any, **kwargs: Any):
        raise RuntimeError("unsupported")