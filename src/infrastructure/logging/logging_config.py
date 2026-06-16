"""Configuração de logs estruturados."""

from __future__ import annotations

import logging
import os


LOG_FORMAT = (
    "%(asctime)s %(levelname)s [%(name)s] "
    "process=%(process)d thread=%(thread)d operation=%(executed_operation)s %(message)s"
)


class OperationFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "executed_operation"):
            record.executed_operation = "-"
        return True


def configure_logging() -> None:
    level_name = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(level=level, format=LOG_FORMAT, force=True)
    for handler in logging.getLogger().handlers:
        handler.addFilter(OperationFilter())
