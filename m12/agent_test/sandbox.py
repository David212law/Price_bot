"""Sandbox — کپی ایزوله پروژه برای آزمایش."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from agent_lib.core import REPO


EXCLUDE_IN_SANDBOX = frozenset({
    ".git", "__pycache__", "node_modules", "venv", ".venv",
    "archive", "m12/cache", "data", ".agent_backups",
    "m12/agent_lib/reports",
})

SANDBOX_PREFIXES = ("pricebot_sandbox_", "pb_exp_", "pb_sandbox")


def make_sandbox(
    source: Path | None = None,
    dest: Path | None = None,
    max_files: int = 200,
) -> Path:
    source = source or REPO
    if dest is None:
        dest = Path(tempfile.mkdtemp(prefix="pricebot_sandbox_"))
    else:
        dest = Path(dest)
        dest.mkdir(parents=True, exist_ok=True)

    print(f"📦 Creating sandbox: {dest}")
    print(f"   from: {source}")

    count = 0
    for py in source.rglob("*.py"):
        try:
            rel = py.relative_to(source)
        except ValueError:
            continue
        parts = rel.parts
        if any(part in EXCLUDE_IN_SANDBOX for part in parts):
            continue
        if py.suffix == ".bak" or ".bak_" in py.name:
            continue

        dst = dest / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(py, dst)
        count += 1
        if count >= max_files:
            print(f"   ⚠  reached max_files={max_files}, stopping")
            break

    for extra in ["m12/config.json", "m12/agent_health.json", "data/kill_switch_active.json"]:
        src_file = source / extra
        if src_file.exists():
            dst = dest / extra
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst)

    print(f"   ✅ {count} .py files copied")
    return dest


def cleanup_sandbox(sandbox: Path, keep: bool = False) -> None:
    if keep:
        print(f"💾 Sandbox kept: {sandbox}")
        return
    name = sandbox.name
    if sandbox.exists() and any(name.startswith(p) for p in SANDBOX_PREFIXES):
        shutil.rmtree(sandbox)
        print(f"🧹 Sandbox removed: {sandbox}")
    else:
        print(f"⚠  Refusing to remove: {sandbox} (not a sandbox)")
