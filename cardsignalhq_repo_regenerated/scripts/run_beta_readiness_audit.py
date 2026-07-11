#!/usr/bin/env python3
"""Run internal beta-readiness audit and print JSON summary."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cardchase_ai.beta_readiness import run_beta_readiness_audit
from cardchase_ai.config import get_settings


def main() -> int:
    settings = get_settings()
    supabase_configured = bool(settings.supabase_url and settings.supabase_service_role_key)
    result = run_beta_readiness_audit(supabase_configured=supabase_configured, settings=settings)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.status != "NOT_READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
