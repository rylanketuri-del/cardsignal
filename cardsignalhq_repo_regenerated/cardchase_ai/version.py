"""Centralized application version and build metadata."""

from __future__ import annotations

import os

APP_VERSION = "0.14.1"
BUILD_ID = os.getenv("BUILD_ID", "e94a5c1")
PRODUCT_LABEL = "CardSignal Beta"
ALGORITHM_VERSION = "WEEKLY_INTELLIGENCE_V1"


def get_app_info() -> dict[str, str]:
    return {
        "product_label": PRODUCT_LABEL,
        "app_version": APP_VERSION,
        "build_id": BUILD_ID,
        "algorithm_version": ALGORITHM_VERSION,
    }
