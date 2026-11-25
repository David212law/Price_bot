"""
Agent Core — انواع داده مشترک و ابزارهای پایه.

اصل: هر detector فقط detect می‌کنه، هر fixer فقط fix.
هیچ‌کدام تصمیم نهایی نمی‌گیرن — orchestrator تصمیم می‌گیره.
"""
from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

# ─────────────────────────────────────────────
# انواع داده
# ─────────────────────────────────────────────

Severity = Literal["info", "warning", "error", "critical"]
Decision = Literal["auto_fix", "suggest", "ignore", "needs_human"]


@dataclass
class Violation:
    """یک مشکل کشف‌شده در یک فایل."""
    file: str
    lineno: int
    col: int
    rule: str                    # نام detector/rule
    severity: Severity
    message: str
    auto_fixable: bool = False   # آیا fixer امن داره؟
    context: str = ""            # خط کد برای review
    detector: str = ""           # کدوم detector اینو پیدا کرد

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FixResult:
    """نتیجه اعمال یک fixer."""
    file: str
    rule: str
    applied: bool
    reason: str = ""
    verifier_passed: bool = False
    diff_lines: int = 0
    duration_ms: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DetectorStats:
    """آمار اجرای یک detector."""
    name: str
    files_scanned: int = 0
    violations: int = 0
    errors: int = 0
    duration_ms: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RunReport:
    """گزارش کامل یک اجرا."""
    run_id: str
    started_at: str
    finished_at: str = ""
    detectors: list[DetectorStats] = field(default_factory=list)
    violations: list[Violation] = field(default_factory=list)
    fixes: list[FixResult] = field(default_factory=list)
    decisions: dict[str, int] = field(default_factory=dict)
    git_dirty_files: int = 0
    python_version: str = ""
    platform: str = ""

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "detectors": [d.to_dict() for d in self.detectors],
            "violations": [v.to_dict() for v in self.violations],
            "fixes": [f.to_dict() for f in self.fixes],
            "decisions": self.decisions,
            "git_dirty_files": self.git_dirty_files,
            "python_version": self.python_version,
            "platform": self.platform,
        }

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False))


# ─────────────────────────────────────────────
# ابزارهای پایه
# ─────────────────────────────────────────────

REPO = Path(__file__).resolve().parents[2]
PY_FILES_CACHE: list[Path] | None = None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def make_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="replace")).hexdigest()[:12]


# پوشه‌هایی که هرگز نباید اسکن/fix بشن
EXCLUDE_DIRS = frozenset({
    ".git", "__pycache__", "node_modules", "venv", ".venv",
    "archive",          # بکاپ‌های تاریخی
    ".agent_backups",   # بکاپ‌های خود agent
    "m12/cache",        # کش دیتا (JSON)
    "agent/tests/fixtures",  # fixture های تست
})


def iter_python_files(
    root: Path | None = None,
    exclude: frozenset[str] = EXCLUDE_DIRS,
) -> list[Path]:
    """همه فایل‌های .py پروژه (بدون پوشه‌های exclude)."""
    root = root or REPO
    out: list[Path] = []
    for p in root.rglob("*.py"):
        # مسیر نسبی به root
        try:
            rel_parts = p.relative_to(root).parts
        except ValueError:
            rel_parts = p.parts
        # اگه هر بخشی در exclude بود، skip
        if any(part in exclude for part in rel_parts):
            continue
        # skip backup files
        if p.suffix in (".bak", ".bak_old") or p.name.endswith(".bak"):
            continue
        out.append(p)
    return sorted(out)


def parse_ast_safe(path: Path) -> ast.AST | None:
    """parse امن؛ اگه syntax error داشت None برمی‌گردونه."""
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return None


def read_text_safe(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def git(*args: str, cwd: Path | None = None) -> str:
    """اجرای git و برگردوندن stdout (بدون raise)."""
    try:
        r = subprocess.run(
            ["git", *args],
            cwd=str(cwd or REPO),
            capture_output=True,
            text=True,
            timeout=60,
        )
        return r.stdout
    except Exception:
        return ""


def git_dirty_count() -> int:
    return len([l for l in git("status", "--short").splitlines() if l.strip()])


def git_head() -> str:
    return git("rev-parse", "--short", "HEAD").strip()


def get_runtime_info() -> dict:
    return {
        "python_version": sys.version.split()[0],
        "platform": sys.platform,
    }


class Timer:
    """زمان‌سنج context manager."""
    def __init__(self):
        self.ms = 0.0

    def __enter__(self):
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.ms = (time.perf_counter() - self._t0) * 1000


# ─────────────────────────────────────────────
# Base Detector
# ─────────────────────────────────────────────

class BaseDetector:
    """کلاس پایه detector ها. هر detector باید name و detect داشته باشه."""
    name: str = "base"

    def detect(self, path: Path, tree: ast.AST) -> list[Violation]:
        raise NotImplementedError

    def run(self, files: list[Path]) -> tuple[list[Violation], DetectorStats]:
        stats = DetectorStats(name=self.name)
        violations: list[Violation] = []
        t = Timer()
        with t:
            for p in files:
                tree = parse_ast_safe(p)
                if tree is None:
                    stats.errors += 1
                    continue
                stats.files_scanned += 1
                try:
                    violations.extend(self.detect(p, tree))
                except Exception as e:
                    stats.errors += 1
                    print(f"[{self.name}] error on {p.name}: {e}", file=sys.stderr)
        stats.violations = len(violations)
        stats.duration_ms = round(t.ms, 2)
        return violations, stats


# ─────────────────────────────────────────────
# AST helpers (برای detectors)
# ─────────────────────────────────────────────

def node_line(node: ast.AST) -> int:
    return getattr(node, "lineno", 0)


def node_col(node: ast.AST) -> int:
    return getattr(node, "col_offset", 0)


def source_line(source: str, lineno: int) -> str:
    if not source or lineno < 1:
        return ""
    lines = source.splitlines()
    if lineno <= len(lines):
        return lines[lineno - 1].strip()
    return ""


def ast_dump_short(node: ast.AST) -> str:
    return ast.dump(node, annotate_fields=False)[:120]


__all__ = [
    # types
    "Violation", "FixResult", "DetectorStats", "RunReport",
    "Severity", "Decision",
    # paths & utils
    "REPO", "now_iso", "make_run_id", "sha1",
    "iter_python_files", "parse_ast_safe", "read_text_safe",
    "git", "git_dirty_count", "git_head", "get_runtime_info", "Timer",
    # base
    "BaseDetector",
    # ast helpers
    "node_line", "node_col", "source_line", "ast_dump_short",
]
