import pytest

from core.config import ConfigError, Settings


def test_defaults_are_private_and_off():
    s = Settings.from_env({})
    assert s.external_enabled is False and s.policy_default == "local_only" and s.nim_api_key == ""
    assert s.nim_base_url == "https://integrate.api.nvidia.com/v1" and s.external_retry_max == 1
    assert s.nim_enable_thinking is False and s.external_daily_call_limit == 100


def test_phase4_env_parsing():
    s = Settings.from_env({"VISTA_EXTERNAL_ENABLED": "true", "VISTA_POLICY_DEFAULT": "Hybrid",
                           "VISTA_NIM_API_KEY": "nvapi-abcdefgh12345", "VISTA_EXTERNAL_RETRY_MAX": "3",
                           "VISTA_EXTERNAL_TIMEOUT_SECONDS": "12.5", "VISTA_NIM_MAX_TOKENS": "256",
                           "VISTA_UNDERSTANDING_MAX_SIDE": "512", "VISTA_EXTERNAL_DAILY_CALL_LIMIT": "5"})
    assert (s.external_enabled, s.policy_default, s.external_retry_max) == (True, "hybrid", 3)
    assert (s.external_timeout_seconds, s.nim_max_tokens, s.understanding_max_side) == (12.5, 256, 512)
    assert s.nim_api_key == "nvapi-abcdefgh12345" and s.external_daily_call_limit == 5


@pytest.mark.parametrize("name,value", [
    ("VISTA_POLICY_DEFAULT", "auto"), ("VISTA_EXTERNAL_ENABLED", "maybe"), ("VISTA_EXTERNAL_RETRY_MAX", "4"),
    ("VISTA_EXTERNAL_RETRY_MAX", "-1"), ("VISTA_EXTERNAL_TIMEOUT_SECONDS", "0"),
    ("VISTA_EXTERNAL_TIMEOUT_SECONDS", "nan"), ("VISTA_NIM_BASE_URL", "http://integrate.api.nvidia.com/v1"),
    ("VISTA_NIM_BASE_URL", "https://evil.example.com/v1"), ("VISTA_NIM_MODEL", "bad model name"),
    ("VISTA_NIM_API_KEY", "has space in it 12345"), ("VISTA_NIM_API_KEY", "short"),
    ("VISTA_NIM_MAX_TOKENS", "1"), ("VISTA_NIM_MAX_IMAGE_BYTES", "5"), ("VISTA_UNDERSTANDING_MAX_SIDE", "8"),
    ("VISTA_EXTERNAL_DAILY_CALL_LIMIT", "0")])
def test_invalid_phase4_config_names_the_variable_not_the_value(name, value):
    with pytest.raises(ConfigError) as e:
        Settings.from_env({name: value})
    assert name in str(e.value)
    if name == "VISTA_NIM_API_KEY":
        assert value not in str(e.value)
