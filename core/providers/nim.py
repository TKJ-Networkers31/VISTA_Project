"""NVIDIA NIM adapter (hosted, OpenAI-compatible /chat/completions) for the `image_understanding` capability.

Request shape: taken from NVIDIA's own example for nvidia/nemotron-3-nano-omni-30b-a3b-reasoning. The response shape
(choices[0].message.content), the inline image size limit and the effect of `enable_thinking` are NOT verified until a
live run (tests/test_nim_real.py). This adapter does NOT do OCR and does NOT return bounding boxes.

Security: https + host allow-list, no redirects (the Authorization header never leaves the allowed host), the key is
only used to build the header and never appears in errors or logs, transport errors are mapped to fixed messages.
"""
from __future__ import annotations

import base64
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple
from urllib.parse import urlparse

from core.config import NIM_ALLOWED_HOSTS, NIM_DEFAULT_BASE_URL, NIM_DEFAULT_MODEL
from core.contracts import VistaError
from core.routing.budget import CallBudget

MAX_ANSWER_CHARS = 8000
MAX_RESPONSE_BYTES = 2_000_000
RETRYABLE_STATUS = (429, 503)
_THINK = re.compile(r"^\s*<think>.*?</think>\s*", re.S)

Transport = Callable[[str, Dict[str, str], bytes, float], Tuple[int, Dict[str, str], bytes]]


@dataclass(frozen=True)
class NimConfig:
    api_key: str = field(default="", repr=False)
    base_url: str = NIM_DEFAULT_BASE_URL
    model: str = NIM_DEFAULT_MODEL
    timeout_seconds: float = 30.0  # per HTTP attempt
    max_tokens: int = 1024
    enable_thinking: bool = False
    max_retries: int = 1  # extra attempts, only for 429/503; bounded


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # a 3xx becomes an HTTPError: the Authorization header is never replayed elsewhere


_OPENER = urllib.request.build_opener(_NoRedirect)


def _urllib_transport(url: str, headers: Dict[str, str], body: bytes, timeout: float):
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with _OPENER.open(req, timeout=timeout) as resp:  # https and host allow-list were checked in validate_config
            return resp.status, dict(resp.headers), resp.read(MAX_RESPONSE_BYTES)
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read(200_000)


def validate_config(cfg: NimConfig) -> None:
    parsed = urlparse(cfg.base_url)
    if parsed.scheme != "https" or parsed.hostname not in NIM_ALLOWED_HOSTS:
        raise VistaError("invalid_input", "NIM_BASE_URL_INVALID", "The NIM base URL must be https on an allowed host.")
    if not cfg.model or len(cfg.model) > 128:
        raise VistaError("invalid_input", "NIM_MODEL_INVALID", "The NIM model name is invalid.")


class NimAdapter:
    supports = frozenset({"image_understanding"})
    provider_id = "nvidia-nim"

    def __init__(self, cfg: NimConfig, budget: Optional[CallBudget] = None, transport: Optional[Transport] = None,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        validate_config(cfg)
        self.cfg, self.budget = cfg, budget
        self._send = transport or _urllib_transport
        self._sleep = sleep

    # -- identity (never includes the key) --
    def is_configured(self) -> bool:
        return bool(self.cfg.api_key)

    def describe(self) -> Dict[str, Any]:
        info: Dict[str, Any] = {"provider": self.provider_id, "model": self.cfg.model,
                                "host": urlparse(self.cfg.base_url).hostname, "supports": sorted(self.supports),
                                "timeout_seconds_per_attempt": self.cfg.timeout_seconds,
                                "max_retries": self.cfg.max_retries}
        if self.budget is not None:
            info["calls_used_today"] = self.budget.used()
            info["daily_call_limit"] = self.budget.daily_limit
        return info

    # -- request --
    def _payload(self, jpeg: bytes, question: str) -> bytes:
        data_uri = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")
        payload = {
            "model": self.cfg.model, "stream": False, "max_tokens": self.cfg.max_tokens,
            "temperature": 0.6, "top_p": 0.95,
            "chat_template_kwargs": {"enable_thinking": self.cfg.enable_thinking},
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": question},
                {"type": "image_url", "image_url": {"url": data_uri}},
            ]}],
        }
        return json.dumps(payload).encode("utf-8")

    def ask(self, jpeg: bytes, question: str, on_send: Optional[Callable[[], None]] = None) -> str:
        """Send one image and one question. `on_send` is called right before every HTTP attempt."""
        if not self.is_configured():
            raise VistaError("unavailable", "NIM_NOT_CONFIGURED", "The external provider has no credentials.")
        body = self._payload(jpeg, question)
        headers = {"Authorization": "Bearer " + self.cfg.api_key, "Accept": "application/json",
                   "Content-Type": "application/json"}
        url = self.cfg.base_url.rstrip("/") + "/chat/completions"
        for attempt in range(self.cfg.max_retries + 1):
            if self.budget is not None and not self.budget.acquire():
                raise VistaError("resource_limit", "BUDGET_EXCEEDED",
                                 "The daily limit of external calls was reached.", retryable=False,
                                 details={"daily_call_limit": self.budget.daily_limit})
            if on_send is not None:
                on_send()
            try:
                status, _headers, raw = self._send(url, headers, body, self.cfg.timeout_seconds)
            except TimeoutError:
                raise VistaError("timeout", "NIM_TIMEOUT", "The external provider timed out.", True) from None
            except urllib.error.URLError as exc:
                if isinstance(exc.reason, TimeoutError):
                    raise VistaError("timeout", "NIM_TIMEOUT", "The external provider timed out.", True) from None
                raise VistaError("unavailable", "NIM_NETWORK", "The external provider is unreachable.", True) from None
            except OSError:
                raise VistaError("unavailable", "NIM_NETWORK", "The external provider is unreachable.", True) from None
            if status in RETRYABLE_STATUS and attempt < self.cfg.max_retries:
                self._sleep(min(2.0, 0.5 * (attempt + 1)))
                continue
            return self._parse(status, raw)
        raise VistaError("provider_internal", "NIM_SERVER_ERROR", "The external provider failed.")  # not reachable

    @staticmethod
    def _parse(status: int, raw: bytes) -> str:
        if status in (401, 403):
            raise VistaError("provider_internal", "NIM_AUTH_FAILED", "The external provider rejected the credentials.")
        if status == 429:
            raise VistaError("resource_limit", "NIM_RATE_LIMITED", "The external provider rate limit was hit.", True)
        if status in (400, 422):
            raise VistaError("provider_internal", "NIM_BAD_REQUEST", "The external provider rejected the request.")
        if status != 200:
            raise VistaError("provider_internal", "NIM_SERVER_ERROR", "The external provider failed.", status >= 500)
        try:
            text = json.loads(raw)["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            raise VistaError("provider_internal", "NIM_MALFORMED",
                             "The external provider sent an unexpected response.") from None
        if not isinstance(text, str):
            raise VistaError("provider_internal", "NIM_MALFORMED", "The external provider sent an unexpected response.")
        text = _THINK.sub("", text).strip()
        if not text:
            raise VistaError("provider_internal", "NIM_EMPTY", "The external provider returned no text.")
        return text[:MAX_ANSWER_CHARS]
