"""
Structured logging, sensitive data redaction filter, and request tracking.
"""
import contextvars
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict

# Context variable to correlate logs with incoming HTTP request IDs
request_id_ctx_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")

# Redaction patterns
REDACTION_PATTERNS = [
    # Passwords in JSON / query / text: password=..., "password": "...", "password_hash": "..."
    (re.compile(r'(?i)(["\']?(?:password|password_hash|passwd)["\']?\s*[:=]\s*["\'])([^"\']+)(["\'])'), r'\1[REDACTED]\3'),
    # Bearer tokens in headers: Bearer ey...
    (re.compile(r'(?i)(Bearer\s+)([A-Za-z0-9\-_\.]+)'), r'\1[REDACTED]'),
    # Standalone JWT patterns: eyJ...
    (re.compile(r'eyJ[A-Za-z0-9\-_]{15,}\.[A-Za-z0-9\-_]{15,}\.[A-Za-z0-9\-_]{15,}'), r'[REDACTED_JWT]'),
    # Full Database URLs with credentials: postgresql+asyncpg://user:secret@host/db
    (re.compile(r'(?i)(postgres(?:ql)?(?:\+[a-z0-9_]+)?://[^:\s]+:)([^@\s]+)(@.+)'), r'\1[REDACTED]\3'),
    # API keys: ORS_API_KEY=..., api_key: "..."
    (re.compile(r'(?i)(["\']?(?:ors_api_key|api_key|secret_key|jwt_secret)["\']?\s*[:=]\s*["\']?)([A-Za-z0-9\-_]{8,})(["\']?)'), r'\1[REDACTED]\3'),
]


def redact_sensitive_text(text: str) -> str:
    """Apply all sensitive redaction rules to a given string."""
    if not isinstance(text, str):
        text = str(text)
    for pattern, replacement in REDACTION_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class SensitiveDataRedactingFilter(logging.Filter):
    """
    Log filter that scans and redacts passwords, tokens, API keys, and database credentials
    from log records before emission.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if isinstance(record.msg, str):
                record.msg = redact_sensitive_text(record.msg)
            if record.args:
                if isinstance(record.args, dict):
                    record.args = {k: redact_sensitive_text(v) if isinstance(v, str) else v for k, v in record.args.items()}
                elif isinstance(record.args, (list, tuple)):
                    record.args = tuple(redact_sensitive_text(v) if isinstance(v, str) else v for v in record.args)
        except Exception:
            pass
        return True


class JsonLogFormatter(logging.Formatter):
    """
    Structured JSON log formatter for production observability.
    """

    def format(self, record: logging.LogRecord) -> str:
        req_id = request_id_ctx_var.get()
        payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if req_id:
            payload["request_id"] = req_id
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(is_production: bool = False) -> None:
    """Configure root and application loggers with the redaction filter and formatters."""
    root_logger = logging.getLogger()
    redaction_filter = SensitiveDataRedactingFilter()

    for handler in root_logger.handlers:
        handler.addFilter(redaction_filter)
        if is_production:
            handler.setFormatter(JsonLogFormatter())

    smartroute_logger = logging.getLogger("smartroute")
    smartroute_logger.addFilter(redaction_filter)
