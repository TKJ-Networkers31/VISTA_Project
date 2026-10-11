"""Run: python -m apps.api   (binds to VISTA_HOST, default 127.0.0.1)"""
import logging
from pathlib import Path

import uvicorn

from core.config import ConfigError, Settings, load_dotenv


def main() -> None:
    env_file = Path.cwd() / ".env"
    load_dotenv(env_file)
    try:
        settings = Settings.from_env()
    except ConfigError as err:
        raise SystemExit(f"Configuration error: {err}") from None
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    # Effective values (never the key): proves which settings the running server really uses.
    logging.getLogger("vista.config").info(
        "env_file_found=%s external_enabled=%s policy_default=%s external_timeout=%ss retry_max=%s "
        "task_timeout=%ss nim_model=%s nim_key_set=%s understanding_max_side=%s",
        env_file.is_file(), settings.external_enabled, settings.policy_default, settings.external_timeout_seconds,
        settings.external_retry_max, settings.task_timeout_seconds, settings.nim_model, bool(settings.nim_api_key),
        settings.understanding_max_side)
    from apps.api.main import create_app

    uvicorn.run(create_app(settings), host=settings.host, port=settings.port, log_level=settings.log_level.lower())


if __name__ == "__main__":
    main()
