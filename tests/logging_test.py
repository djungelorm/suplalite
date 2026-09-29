import logging.config
from typing import Any

import pytest

from suplalite.logging import configure_logging, get_config


def test_get_config() -> None:
    config = get_config(level="INFO")
    assert config["formatters"]["default"]["format"].startswith("%(asctime)s ")
    assert config["root"]["level"] == "INFO"
    assert config["loggers"]["suplalite"]["level"] == "INFO"
    assert config["loggers"]["uvicorn"]["level"] == "INFO"


def test_get_config_without_time() -> None:
    config = get_config(show_time=False)
    assert "%(asctime)s" not in config["formatters"]["default"]["format"]


def test_configure_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    # Note: a real dictConfig would disable the loggers other tests capture
    configs: list[dict[str, Any]] = []
    monkeypatch.setattr(logging.config, "dictConfig", configs.append)
    configure_logging(show_time=False, level="INFO")
    assert configs == [get_config(show_time=False, level="INFO")]
