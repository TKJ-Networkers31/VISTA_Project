"""NVIDIA NIM adapter against a fake transport. No network, no key. Proves request shape, error mapping, bounds."""
import base64
import json
import urllib.error

import pytest

from core.contracts import VistaError
from core.providers.nim import NimAdapter, NimConfig, _NoRedirect
from core.routing import CallBudget

KEY = "nvapi-SECRET-KEY-0123456789"
JPEG = b"\xff\xd8\xff\xe0fakejpegbytes"


def ok(text="A red square."):
    return 200, {}, json.dumps({"choices": [{"message": {"role": "assistant", "content": text}}]}).encode()


class Transport:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    def __call__(self, url, headers, body, timeout):
        self.calls.append((url, headers, body, timeout))
        item = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(item, BaseException):
            raise item
        return item


def adapter(*responses, retries=1, budget=None, **cfg):
    t = Transport(*responses)
    a = NimAdapter(NimConfig(api_key=cfg.pop("api_key", KEY), max_retries=retries, **cfg), budget=budget,
                   transport=t, sleep=lambda s: None)
    return a, t


def code(excinfo):
    return excinfo.value.code


def test_request_shape_matches_the_documented_example():
    a, t = adapter(ok())
    assert a.ask(JPEG, "What is this?") == "A red square."
    url, headers, body, timeout = t.calls[0]
    assert url == "https://integrate.api.nvidia.com/v1/chat/completions" and timeout == 30.0
    assert headers["Authorization"] == "Bearer " + KEY
    payload = json.loads(body)
    assert payload["model"] == "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning" and payload["stream"] is False
    assert payload["max_tokens"] == 1024 and payload["chat_template_kwargs"] == {"enable_thinking": False}
    parts = payload["messages"][0]["content"]
    assert parts[0] == {"type": "text", "text": "What is this?"}
    uri = parts[1]["image_url"]["url"]
    assert uri.startswith("data:image/jpeg;base64,") and base64.b64decode(uri.split(",", 1)[1]) == JPEG
    assert KEY.encode() not in body  # the key is only ever in the header


def test_on_send_is_called_before_each_attempt():
    a, _ = adapter((429, {}, b""), ok())
    sent = []
    a.ask(JPEG, "q", on_send=lambda: sent.append(1))
    assert len(sent) == 2


def test_think_block_is_stripped_and_answer_is_capped():
    a, _ = adapter(ok("<think>hidden</think>\n\nBlue."))
    assert a.ask(JPEG, "q") == "Blue."
    a, _ = adapter(ok("x" * 20000))
    assert len(a.ask(JPEG, "q")) == 8000


@pytest.mark.parametrize("status,expected", [(401, "NIM_AUTH_FAILED"), (403, "NIM_AUTH_FAILED"),
                                             (400, "NIM_BAD_REQUEST"), (422, "NIM_BAD_REQUEST"),
                                             (500, "NIM_SERVER_ERROR"), (502, "NIM_SERVER_ERROR"),
                                             (302, "NIM_SERVER_ERROR")])
def test_status_mapping(status, expected):
    a, t = adapter((status, {}, b"{}"))
    with pytest.raises(VistaError) as e:
        a.ask(JPEG, "q")
    assert code(e) == expected and len(t.calls) == 1  # these are never retried


def test_rate_limit_retries_are_bounded():
    a, t = adapter((429, {}, b""), retries=2)
    with pytest.raises(VistaError) as e:
        a.ask(JPEG, "q")
    assert code(e) == "NIM_RATE_LIMITED" and e.value.retryable and e.value.category == "resource_limit"
    assert len(t.calls) == 3  # 1 + 2 retries, then it stops


def test_503_then_success_and_zero_retries():
    a, t = adapter((503, {}, b""), ok(), retries=1)
    assert a.ask(JPEG, "q") == "A red square." and len(t.calls) == 2
    a, t = adapter((503, {}, b""), retries=0)
    with pytest.raises(VistaError):
        a.ask(JPEG, "q")
    assert len(t.calls) == 1


@pytest.mark.parametrize("raw", [b"not json", b"{}", b'{"choices": []}', b'{"choices": [{"message": {}}]}',
                                 b'{"choices": [{"message": {"content": 5}}]}'])
def test_malformed_responses(raw):
    a, _ = adapter((200, {}, raw))
    with pytest.raises(VistaError) as e:
        a.ask(JPEG, "q")
    assert code(e) == "NIM_MALFORMED"


def test_empty_answer_after_thinking_only():
    a, _ = adapter(ok("<think>only thoughts</think>"))
    with pytest.raises(VistaError) as e:
        a.ask(JPEG, "q")
    assert code(e) == "NIM_EMPTY"


def test_timeouts_and_network_errors_are_not_retried():
    for exc, expected in [(TimeoutError(), "NIM_TIMEOUT"),
                          (urllib.error.URLError(TimeoutError()), "NIM_TIMEOUT"),
                          (urllib.error.URLError("dns failure for host"), "NIM_NETWORK"),
                          (ConnectionResetError(), "NIM_NETWORK")]:
        a, t = adapter(exc, retries=3)
        with pytest.raises(VistaError) as e:
            a.ask(JPEG, "q")
        assert code(e) == expected and len(t.calls) == 1


def test_no_key_means_no_call():
    a, t = adapter(ok(), api_key="")
    assert a.is_configured() is False
    with pytest.raises(VistaError) as e:
        a.ask(JPEG, "q")
    assert code(e) == "NIM_NOT_CONFIGURED" and t.calls == []


def test_budget_stops_calls_and_counts_retries():
    budget = CallBudget(2)
    a, t = adapter((429, {}, b""), retries=5, budget=budget)
    with pytest.raises(VistaError) as e:
        a.ask(JPEG, "q")
    assert code(e) == "BUDGET_EXCEEDED" and len(t.calls) == 2 and budget.remaining() == 0
    with pytest.raises(VistaError):
        a.ask(JPEG, "q")
    assert len(t.calls) == 2  # nothing more was sent


@pytest.mark.parametrize("url", ["http://integrate.api.nvidia.com/v1", "https://evil.example.com/v1",
                                 "https://integrate.api.nvidia.com.evil.example/v1", "ftp://integrate.api.nvidia.com"])
def test_base_url_must_be_https_on_the_allowed_host(url):
    with pytest.raises(VistaError) as e:
        NimAdapter(NimConfig(api_key=KEY, base_url=url))
    assert code(e) == "NIM_BASE_URL_INVALID"


def test_errors_and_describe_never_contain_the_key():
    a, _ = adapter((401, {}, KEY.encode()))
    with pytest.raises(VistaError) as e:
        a.ask(JPEG, "q")
    assert KEY not in str(e.value) and KEY not in repr(e.value.details)
    assert KEY not in json.dumps(a.describe()) and KEY not in repr(a.cfg)


def test_redirects_are_refused():
    assert _NoRedirect().redirect_request(None, None, 302, "Found", {}, "https://elsewhere.example/") is None
