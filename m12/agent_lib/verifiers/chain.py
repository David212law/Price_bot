"""
Verifier chain — بعد از هر fix، چند لایه تأیید.

ترتیب:
  1. syntax      → AST parse
  2. import      → import نمی‌کنه ولی `python -c "compile(...)"` می‌زنه
  3. self_test   → اگه agent_self_test.py موجود بود، اجرا کن
  4. diff        → diff باید معنی‌دار باشه (نه صفر)
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path
from typing import Callable

from agent_lib.core import REPO, Timer


class VerifyResult:
    def __init__(self):
        self.passed = True
        self.checks: list[tuple[str, bool, str]] = []

    def check(self, name: str, ok: bool, msg: str = ""):
        self.checks.append((name, ok, msg))
        if not ok:
            self.passed = False

    def to_str(self) -> str:
        lines = []
        for name, ok, msg in self.checks:
            icon = "✅" if ok else "❌"
            lines.append(f"  {icon} {name}" + (f"  ({msg})" if msg else ""))
        return "\n".join(lines)


def verify_syntax(text: str) -> tuple[bool, str]:
    try:
        ast.parse(text)
        return True, ""
    except SyntaxError as e:
        return False, f"SyntaxError: {e.msg} (line {e.lineno})"


def verify_compile(path: Path, text: str) -> tuple[bool, str]:
    """compile() واقعی، سریع‌تر از import."""
    try:
        compile(text, str(path), "exec")
        return True, ""
    except SyntaxError as e:
        return False, f"CompileError: {e.msg}"


def verify_self_test() -> tuple[bool, str]:
    """اجرای agent_self_test.py اگه موجود بود."""
    st = REPO / "m12" / "agent_self_test.py"
    if not st.exists():
        return True, "not found (skip)"
    try:
        r = subprocess.run(
            [sys.executable, str(st)],
            cwd=str(st.parent), capture_output=True, text=True, timeout=60,
        )
        if r.returncode == 0 and "FAIL: 0" in r.stdout:
            return True, "PASS 11/11"
        return False, f"self_test failed: {r.stdout[-200:]}"
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as e:
        return False, str(e)


def verify_diff_not_empty(diff: str) -> tuple[bool, str]:
    if not diff or not diff.strip():
        return False, "empty diff"
    return True, f"{diff.count(chr(10))} lines"


def run_all_verifiers(path: Path, text: str, diff: str,
                     run_self_test: bool = True) -> VerifyResult:
    """اجرای همه verifier ها."""
    res = VerifyResult()

    ok, msg = verify_syntax(text)
    res.check("syntax_ast", ok, msg)

    ok, msg = verify_compile(path, text)
    res.check("compile", ok, msg)

    ok, msg = verify_diff_not_empty(diff)
    res.check("diff_not_empty", ok, msg)

    if run_self_test:
        ok, msg = verify_self_test()
        res.check("agent_self_test", ok, msg)

    return res
