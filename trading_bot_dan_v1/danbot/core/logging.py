from __future__ import annotations

import json
import logging
import re
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

_LOG_DIR = Path("logs")
_MAX_BYTES = 10 * 1024 * 1024
_BACKUP_COUNT = 10
_SECRET_KEYS = {"api_secret", "secret", "signature", "passphrase"}
_KEY_MASK_RE = re.compile(r"([A-Za-z0-9]{4})[A-Za-z0-9]+([A-Za-z0-9]{4})")


class _SensitiveDataFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = sanitize_for_logging(record.msg)
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(sanitize_for_logging(arg) for arg in record.args)
            elif isinstance(record.args, dict):
                record.args = {k: sanitize_for_logging(v) for k, v in record.args.items()}
        return True


def mask_api_key(value: str) -> str:
    raw = (value or "").strip()
    if len(raw) <= 8:
        return "****"
    return f"{raw[:4]}****{raw[-4:]}"


def sanitize_for_logging(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, val in value.items():
            lowered = key.lower()
            if lowered in _SECRET_KEYS:
                redacted[key] = "***REDACTED***"
            elif lowered in {"api_key", "key"} and isinstance(val, str):
                redacted[key] = mask_api_key(val)
            else:
                redacted[key] = sanitize_for_logging(val)
        return redacted
    if isinstance(value, (list, tuple)):
        cleaned = [sanitize_for_logging(v) for v in value]
        return tuple(cleaned) if isinstance(value, tuple) else cleaned
    if isinstance(value, str):
        if "API_SECRET" in value.upper():
            return "***REDACTED***"
        return _KEY_MASK_RE.sub(r"\1****\2", value)
    return value


def safe_json(data: dict[str, Any]) -> str:
    return json.dumps(sanitize_for_logging(data), ensure_ascii=False, sort_keys=True)


def setup_logging(level: str = "INFO") -> None:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers.clear()

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(threadName)s] %(module)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )

    all_handler = RotatingFileHandler(
        _LOG_DIR / "danbot.log",
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    all_handler.setLevel(logging.DEBUG)
    all_handler.setFormatter(formatter)
    all_handler.addFilter(_SensitiveDataFilter())

    error_handler = RotatingFileHandler(
        _LOG_DIR / "danbot_error.log",
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.WARNING)
    error_handler.setFormatter(formatter)
    error_handler.addFilter(_SensitiveDataFilter())

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
    console_handler.setFormatter(formatter)
    console_handler.addFilter(_SensitiveDataFilter())

    root.addHandler(all_handler)
    root.addHandler(error_handler)
    root.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
