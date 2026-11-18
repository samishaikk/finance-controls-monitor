"""Structured JSON logging: one JSON object per line, on stderr.

stdout stays free for the human-readable table and reports, so logs can be
shipped to a log system without mixing with normal output.
"""

import json
import logging
import sys
from datetime import datetime, timezone


LOGGER_NAME = "controls_monitor"
RESERVED = {"timestamp", "level", "logger", "event", "exception"}

class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        for key, value in getattr(record, "fields", {}).items():
            payload[f"field_{key}" if key in RESERVED else key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class _StderrHandler(logging.StreamHandler):
    """Looks up sys.stderr at write time, so redirected stderr is respected."""

    def __init__(self):
        super().__init__()
        self._is_controls_monitor_handler = True

    @property
    def stream(self):
        return sys.stderr

    @stream.setter
    def stream(self, value):
        pass


def configure_logging(level="INFO"):
    logger = logging.getLogger(LOGGER_NAME)
    for handler in list(logger.handlers):
        if getattr(handler, "_is_controls_monitor_handler", False):
            logger.removeHandler(handler)
    handler = _StderrHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(level)
    return logger


def log_event(logger, event, level=logging.INFO, **fields):
    logger.log(level, event, extra={"fields": fields})