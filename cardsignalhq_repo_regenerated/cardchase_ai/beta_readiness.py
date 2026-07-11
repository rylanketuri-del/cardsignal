"""Internal beta-readiness audit for closed-beta quality gates."""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from cardchase_ai.version import ALGORITHM_VERSION, APP_VERSION, BUILD_ID

ReadinessStatus = Literal["READY", "READY_WITH_WARNINGS", "NOT_READY"]
BlockerCategory = Literal["DATA", "UX", "SECURITY", "ROUTING", "PERFORMANCE", "CONFIGURATION", "PRODUCT"]


@dataclass
class BetaReadinessBlocker:
    category: BlockerCategory
    message: str
    severity: Literal["blocker", "warning"] = "blocker"


@dataclass
class BetaReadinessResult:
    status: ReadinessStatus
    app_version: str = APP_VERSION
    build_id: str = BUILD_ID
    blockers: list[BetaReadinessBlocker] = field(default_factory=list)
    warnings: list[BetaReadinessBlocker] = field(default_factory=list)
    checks_passed: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "app_version": self.app_version,
            "build_id": self.build_id,
            "blockers": [
                {"category": b.category, "message": b.message, "severity": b.severity}
                for b in self.blockers
            ],
            "warnings": [
                {"category": w.category, "message": w.message, "severity": w.severity}
                for w in self.warnings
            ],
            "checks_passed": self.checks_passed,
        }


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _find_pycache_dirs(root: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "-z"],
            cwd=root,
            capture_output=True,
            text=False,
            check=False,
        )
        if result.returncode != 0:
            return []
        tracked = result.stdout.decode("utf-8", errors="ignore").split("\0")
        return sorted({p.split("/__pycache__")[0] + "/__pycache__" for p in tracked if "/__pycache__/" in p})
    except OSError:
        return []


def _scan_for_secret_patterns(root: Path) -> list[str]:
    patterns = [
        re.compile(r"SUPABASE_SERVICE_ROLE_KEY\s*=\s*['\"][^'\"]{8,}"),
        re.compile(r"sk_live_[A-Za-z0-9]{10,}"),
        re.compile(r"-----BEGIN (RSA |EC )?PRIVATE KEY-----"),
    ]
    hits: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pyc"}:
            continue
        if "node_modules" in path.parts or ".git" in path.parts:
            continue
        text = _read_text(path)
        for pattern in patterns:
            if pattern.search(text):
                hits.append(str(path.relative_to(root)))
                break
    return hits


def run_beta_readiness_audit(
    *,
    supabase_configured: bool | None = None,
    settings: Any | None = None,
) -> BetaReadinessResult:
    root = _repo_root()
    result = BetaReadinessResult(status="READY")

    frontend_app = _read_text(root / "frontend" / "app.js")
    beta_feedback_js = _read_text(root / "frontend" / "beta-feedback.js")
    index_html = _read_text(root / "frontend" / "index.html")
    product_md = _read_text(root / "PRODUCT.md")

    # PRODUCT gates
    if re.search(r"(?<!function\s)csIntelGetPlaceholders\s*\(", frontend_app):
        result.blockers.append(
            BetaReadinessBlocker("PRODUCT", "Placeholder intelligence generator is still callable in app.js", "blocker")
        )
    else:
        result.checks_passed.append("No active placeholder intelligence calls")

    if re.search(r"(?<!function\s)getSignalOfWeekPlaceholderEntry\s*\(", frontend_app):
        result.warnings.append(
            BetaReadinessBlocker("PRODUCT", "Signal-of-week placeholder helper still present (unused path)", "warning")
        )
    else:
        result.checks_passed.append("No signal-of-week placeholder fallback")

    fake_card_names = ("Auric Spark", "Copper Drift", "Velvet Crown")
    if any(name in frontend_app for name in fake_card_names):
        result.warnings.append(
            BetaReadinessBlocker("PRODUCT", "Fabricated card name strings remain in frontend source", "warning")
        )
    else:
        result.checks_passed.append("No fabricated card names in active frontend paths")

    if "algorithm_version" not in frontend_app and "algorithmVersion" not in frontend_app:
        result.blockers.append(
            BetaReadinessBlocker("DATA", "Scouting report does not expose algorithm version", "blocker")
        )
    else:
        result.checks_passed.append("Algorithm version surfaced in reports")

    if ALGORITHM_VERSION not in frontend_app and ALGORITHM_VERSION not in product_md:
        result.warnings.append(
            BetaReadinessBlocker("DATA", f"Algorithm constant {ALGORITHM_VERSION} not referenced in frontend/docs", "warning")
        )

    # UX gates
    required_surfaces = [
        ("player-search-module", "Universal Search", index_html),
        ("player-intelligence-modal", "Scouting Report modal", index_html),
        ("beta-feedback-launcher", "Beta Feedback button", beta_feedback_js),
        ("app-version-footer", "Version footer", index_html),
    ]
    for element_id, label, source in required_surfaces:
        if f'id="{element_id}"' not in source and f"id='{element_id}'" not in source:
            result.blockers.append(
                BetaReadinessBlocker("UX", f"Missing required surface: {label}", "blocker")
            )
        else:
            result.checks_passed.append(f"Surface present: {label}")

    if "beta-feedback.js" not in index_html:
        result.blockers.append(
            BetaReadinessBlocker("UX", "Beta feedback module not loaded in index.html", "blocker")
        )

    if "routing.js" not in index_html:
        result.blockers.append(
            BetaReadinessBlocker("ROUTING", "Client routing module not loaded in index.html", "blocker")
        )
    else:
        result.checks_passed.append("Routing module referenced")

    # ROUTING / navigation
    if "popstate" not in _read_text(root / "frontend" / "routing.js"):
        result.blockers.append(
            BetaReadinessBlocker("ROUTING", "Browser back/forward handling not implemented", "blocker")
        )
    else:
        result.checks_passed.append("popstate routing handler present")

    # SECURITY / SYSTEM
    pycache_dirs = _find_pycache_dirs(root)
    if pycache_dirs:
        result.blockers.append(
            BetaReadinessBlocker("SECURITY", f"Tracked __pycache__ directories found: {len(pycache_dirs)}", "blocker")
        )
    else:
        result.checks_passed.append("No tracked __pycache__ directories")

    secret_hits = _scan_for_secret_patterns(root)
    if secret_hits:
        result.blockers.append(
            BetaReadinessBlocker("SECURITY", f"Potential committed secrets in {len(secret_hits)} file(s)", "blocker")
        )
    else:
        result.checks_passed.append("No obvious committed secrets detected")

    if "formatSafeError" not in frontend_app:
        result.warnings.append(
            BetaReadinessBlocker("UX", "Safe error formatter not present in app.js", "warning")
        )
    else:
        result.checks_passed.append("Safe user-facing error formatter present")

    # CONFIGURATION
    if supabase_configured is False:
        result.warnings.append(
            BetaReadinessBlocker(
                "CONFIGURATION",
                "Supabase is not configured — feedback and auth will be unavailable",
                "warning",
            )
        )
    elif supabase_configured:
        result.checks_passed.append("Supabase configured")

    migration = _read_text(root / "supabase" / "migrations" / "20260711_beta_feedback.sql")
    if "beta_feedback" not in migration:
        result.blockers.append(
            BetaReadinessBlocker("CONFIGURATION", "beta_feedback migration missing", "blocker")
        )
    else:
        result.checks_passed.append("beta_feedback migration present")

    if settings is not None and not getattr(settings, "admin_api_token", ""):
        result.warnings.append(
            BetaReadinessBlocker("CONFIGURATION", "Admin API token not configured", "warning")
        )

    # Version metadata
    version_js = _read_text(root / "frontend" / "version.js")
    if APP_VERSION not in version_js:
        result.blockers.append(
            BetaReadinessBlocker("CONFIGURATION", "Centralized frontend version config missing or stale", "blocker")
        )
    else:
        result.checks_passed.append("Centralized version config present")

    # Final status
    if result.blockers:
        result.status = "NOT_READY"
    elif result.warnings:
        result.status = "READY_WITH_WARNINGS"
    else:
        result.status = "READY"

    return result
