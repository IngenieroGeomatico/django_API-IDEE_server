"""Formateadores de log: consola legible y JSON estructurado."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

EXTRA_FIELDS = (
    "request_id",
    "method",
    "path",
    "status",
    "duration_ms",
    "destination",
    "upstream_status",
)


class RequestIdFilter(logging.Filter):
    """Garantiza que todos los registros tengan ``request_id``."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return True


class JsonFormatter(logging.Formatter):
    """Una línea JSON por registro, apta para agregadores."""

    def format(self, record: logging.LogRecord) -> str:
        data: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                data[field] = value
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False, default=str)


__all__ = ["JsonFormatter", "RequestIdFilter"]
