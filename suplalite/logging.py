import logging.config
from typing import Any


def get_config(show_time: bool = True, level: str = "DEBUG") -> dict[str, Any]:
    if show_time:
        asctime = "%(asctime)s "
    else:
        asctime = ""
    return {
        "version": 1,
        "root": {
            "handlers": ["default"],
            "level": level,
        },
        "loggers": {
            "suplalite": {
                "level": level,
            },
            "uvicorn": {
                "level": "INFO",
            },
            "uvicorn.access": {
                "level": "WARN",
            },
        },
        "formatters": {
            "default": {
                "format": asctime + "[%(levelname)s] [%(name)s] %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            }
        },
        "handlers": {
            "default": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "stream": "ext://sys.stdout",
            },
        },
    }


def configure_logging(show_time: bool = True, level: str = "DEBUG") -> None:
    logging.config.dictConfig(
        get_config(
            show_time,
            level,
        )
    )
