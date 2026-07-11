"""Beta feedback validation, sanitization, and rate limiting."""

from __future__ import annotations

import re
import time
from collections import defaultdict
from typing import Any

from pydantic import BaseModel, Field, field_validator

from cardchase_ai.version import APP_VERSION, BUILD_ID

FEEDBACK_TYPES = frozenset({"CONFUSING", "BUG", "IDEA", "LOVE", "OTHER"})
FEEDBACK_STATUSES = frozenset({"NEW", "REVIEWED", "PLANNED", "CLOSED"})
MAX_MESSAGE_LENGTH = 2000
MIN_MESSAGE_LENGTH = 3
MAX_FIELD_LENGTH = 512
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_SUBMISSIONS = 5

# In-memory rate limit store: client_key -> list[timestamps]
_rate_limit_store: dict[str, list[float]] = defaultdict(list)


class BetaFeedbackRequest(BaseModel):
    feedback_type: str
    message: str
    page_url: str | None = None
    current_route: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    sport: str | None = None
    app_version: str | None = None
    build_id: str | None = None
    browser_summary: str | None = None
    viewport_width: int | None = None
    viewport_height: int | None = None

    @field_validator("feedback_type")
    @classmethod
    def validate_feedback_type(cls, value: str) -> str:
        normalized = str(value or "").strip().upper()
        if normalized not in FEEDBACK_TYPES:
            raise ValueError("Invalid feedback type.")
        return normalized

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        cleaned = sanitize_text(value)
        if len(cleaned) < MIN_MESSAGE_LENGTH:
            raise ValueError("Message is required.")
        if len(cleaned) > MAX_MESSAGE_LENGTH:
            raise ValueError(f"Message must be {MAX_MESSAGE_LENGTH} characters or fewer.")
        return cleaned

    @field_validator(
        "page_url",
        "current_route",
        "entity_type",
        "entity_id",
        "sport",
        "browser_summary",
        mode="before",
    )
    @classmethod
    def trim_optional_text(cls, value: Any) -> str | None:
        if value is None:
            return None
        cleaned = sanitize_text(str(value))
        if not cleaned:
            return None
        return cleaned[:MAX_FIELD_LENGTH]


def sanitize_text(value: str) -> str:
    text = str(value or "").strip()
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    return text


def contains_sensitive_data(payload: dict[str, Any]) -> bool:
    serialized = str(payload).lower()
    blocked = ("password", "bearer ", "authorization", "access_token", "refresh_token", "secret", "api_key")
    return any(token in serialized for token in blocked)


def check_rate_limit(client_key: str) -> bool:
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW_SECONDS
    timestamps = [ts for ts in _rate_limit_store[client_key] if ts >= window_start]
    _rate_limit_store[client_key] = timestamps
    if len(timestamps) >= RATE_LIMIT_MAX_SUBMISSIONS:
        return False
    timestamps.append(now)
    _rate_limit_store[client_key] = timestamps
    return True


def build_feedback_record(
    payload: BetaFeedbackRequest,
    *,
    user_id: str | None = None,
    client_ip: str | None = None,
) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "feedback_type": payload.feedback_type,
        "message": payload.message,
        "page_url": payload.page_url,
        "current_route": payload.current_route,
        "entity_type": payload.entity_type,
        "entity_id": payload.entity_id,
        "sport": payload.sport,
        "app_version": payload.app_version or APP_VERSION,
        "build_id": payload.build_id or BUILD_ID,
        "browser_summary": payload.browser_summary,
        "viewport_width": payload.viewport_width,
        "viewport_height": payload.viewport_height,
        "status": "NEW",
        "client_ip": client_ip,
        # Future hook for optional screenshot storage — not exposed in beta UI.
        "screenshot_ref": None,
    }
