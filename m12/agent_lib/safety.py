"""Safety — محافظت از فایل‌های حیاتی و کنترل تغییرات."""
from __future__ import annotations

from pathlib import Path

from agent_lib.core import REPO


# فایل‌هایی که هرگز نباید خودکار fix بشن
# (چون خود agent یا self_test هستن)
PROTECTED_FILES = frozenset({
    "m12/agent.py",
    "m12/agent_self_test.py",
    "m12/agent/core.py",
    "m12/agent/orchestrator.py",
    "m12/agent/detect_only.py",
    "m12/agent/safety.py",
    "m12/agent/detectors/ast_detector.py",
    "m12/agent/fixers/ast_fixer.py",
    "m12/agent/verifiers/chain.py",
})


def is_protected(path: Path) -> bool:
    """آیا این فایل محافظت‌شده است؟"""
    try:
        rel = path.relative_to(REPO)
    except ValueError:
        return True  # خارج از repo → محافظت
    return str(rel) in PROTECTED_FILES


def should_skip(path: Path) -> tuple[bool, str]:
    """آیا باید این فایل رو skip کنیم؟"""
    if is_protected(path):
        return True, "protected file"
    if not path.exists():
        return True, "file not found"
    return False, ""
