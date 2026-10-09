"""Run: python -m apps.api   (binds to VISTA_HOST, default 127.0.0.1)"""
import logging
from pathlib import Path

import uvicorn

from core.config import ConfigError, Settings, load_dotenv


def main() -> None:
    load_dotenv(Path.cwd() / ".env")
    try:
        settings = Settings.from_env()
    except ConfigError as err:
        raise SystemExit(f"Configuration error: {err}") from None
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    from apps.api.main import create_app

    uvicorn.run(create_app(settings), host=settings.host, port=settings.port, log_level=settings.log_level.lower())


if __name__ == "__main__":
    main()
