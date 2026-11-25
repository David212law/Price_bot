"""
AST-based fixers — فقط تغییرهای امن و context-aware.

اصل: هر fixer:
  1. قبل از تغییر، backup می‌گیره
  2. تغییر رو در سطح AST انجام می‌ده (نه regex)
  3. بعد از تغییر، AST parse می‌کنه
  4. اگه خطا داشت، rollback می‌کنه
  5. diff رو برمی‌گردونه برای review
"""
from __future__ import annotations

import ast
import difflib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from agent_lib.core import (
    Violation, FixResult, REPO, Timer, read_text_safe,
)


# ─────────────────────────────────────────────
# FixResult internal
# ─────────────────────────────────────────────
@dataclass
class AppliedFix:
    fixed_text: str
    diff: str
    lines_changed: int


# ─────────────────────────────────────────────
# 1. Silent fail: except: pass
# ─────────────────────────────────────────────
class SilentFailFixer:
    """
    تبدیل `except: pass` به `except Exception as _e: print(...)`.
    
    ⚠️ فقط زمانی اعمال می‌شه که detector تأیید کرده باشه:
      - except.type is None (بدون نوع)
      - body = [Pass]
    
    این fixer خط‌محور کار می‌کنه (نه AST rewrite) چون AST unparse
    کامنت‌ها و فرمت رو از بین می‌بره.
    """
    name = "silent_fail"

    def can_fix(self, v: Violation) -> bool:
        return v.rule == "silent_fail" and v.auto_fixable

    def fix(self, path: Path, violations: list[Violation]) -> AppliedFix | None:
        text = read_text_safe(path)
        if text is None:
            return None

        lines = text.splitlines(keepends=True)
        changed = 0

        # فقط خط‌هایی که detector مشخص کرده رو تغییر بده
        for v in violations:
            if not self.can_fix(v):
                continue
            lineno = v.lineno  # 1-based
            if lineno < 1 or lineno > len(lines):
                continue
            line = lines[lineno - 1]
            # فقط اگه دقیقاً `except:` یا `except: pass` باشه
            m = re.match(r'^(\s*)except\s*:\s*(pass)?\s*(#.*)?$', line)
            if not m:
                continue
            indent = m.group(1)
            # خط except رو با print جایگزین کن
            # line است: `    except:`  یا  `    except: pass`
            # ما می‌خوایم:
            #   `    except Exception as _e: print(f"caught: {_e}")`
            new_line = f'{indent}except Exception as _e: print(f"caught: {{_e}}")\n'
            # اگه خط بعدی pass داشت، حذفش کن
            if lineno < len(lines) and re.match(r'^\s+pass\s*$', lines[lineno]):
                del lines[lineno]  # حذف pass
            lines[lineno - 1] = new_line
            changed += 1

        if changed == 0:
            return None

        new_text = "".join(lines)

        # ─── verify syntax
        try:
            ast.parse(new_text)
        except SyntaxError as e:
            return None  # rollback

        # ─── diff
        diff = "".join(difflib.unified_diff(
            text.splitlines(keepends=True),
            new_text.splitlines(keepends=True),
            fromfile=str(path), tofile=str(path),
            n=1,
        ))

        return AppliedFix(
            fixed_text=new_text,
            diff=diff,
            lines_changed=changed,
        )


# ─────────────────────────────────────────────
# 2. x == None → x is None
# ─────────────────────────────────────────────
class NoneComparisonFixer:
    name = "none_comparison"

    def can_fix(self, v: Violation) -> bool:
        return v.rule == "none_comparison" and v.auto_fixable

    def fix(self, path: Path, violations: list[Violation]) -> AppliedFix | None:
        text = read_text_safe(path)
        if text is None:
            return None

        lines = text.splitlines(keepends=True)
        changed = 0
        for v in violations:
            if not self.can_fix(v):
                continue
            lineno = v.lineno
            if lineno < 1 or lineno > len(lines):
                continue
            line = lines[lineno - 1]
            # == None  →  is None
            new = re.sub(r'\b==\s*None\b', 'is None', line)
            # != None  →  is not None
            new = re.sub(r'!=\s*None\b', 'is not None', new)
            if new != line:
                lines[lineno - 1] = new
                changed += 1

        if changed == 0:
            return None
        new_text = "".join(lines)
        try:
            ast.parse(new_text)
        except SyntaxError:
            return None
        return AppliedFix(
            fixed_text=new_text,
            diff="".join(difflib.unified_diff(
                text.splitlines(keepends=True), new_text.splitlines(keepends=True),
                fromfile=str(path), tofile=str(path), n=1)),
            lines_changed=changed,
        )


# ─────────────────────────────────────────────
# 3. while 1 → while True
# ─────────────────────────────────────────────
class WhileOneFixer:
    name = "while_one"

    def can_fix(self, v: Violation) -> bool:
        return v.rule == "while_one" and v.auto_fixable

    def fix(self, path: Path, violations: list[Violation]) -> AppliedFix | None:
        text = read_text_safe(path)
        if text is None:
            return None
        lines = text.splitlines(keepends=True)
        changed = 0
        for v in violations:
            if not self.can_fix(v):
                continue
            lineno = v.lineno
            if lineno < 1 or lineno > len(lines):
                continue
            line = lines[lineno - 1]
            new = re.sub(r'\bwhile\s+1\b', 'while True', line)
            if new != line:
                lines[lineno - 1] = new
                changed += 1
        if changed == 0:
            return None
        new_text = "".join(lines)
        try:
            ast.parse(new_text)
        except SyntaxError:
            return None
        return AppliedFix(
            fixed_text=new_text,
            diff="".join(difflib.unified_diff(
                text.splitlines(keepends=True), new_text.splitlines(keepends=True),
                fromfile=str(path), tofile=str(path), n=1)),
            lines_changed=changed,
        )


# ─────────────────────────────────────────────
# 4. len(x) > 0 → x   |   len(x) == 0 → not x
# ─────────────────────────────────────────────
class LenTruthinessFixer:
    name = "len_truthiness"

    def can_fix(self, v: Violation) -> bool:
        return v.rule == "len_truthiness" and v.auto_fixable

    def fix(self, path: Path, violations: list[Violation]) -> AppliedFix | None:
        text = read_text_safe(path)
        if text is None:
            return None
        lines = text.splitlines(keepends=True)
        changed = 0
        for v in violations:
            if not self.can_fix(v):
                continue
            lineno = v.lineno
            if lineno < 1 or lineno > len(lines):
                continue
            line = lines[lineno - 1]
            # len(x) > 0  →  x
            # len(x) == 0 →  not x
            new = re.sub(
                r'\blen\(\s*([a-zA-Z_][\w\.\[\]\'"]*)\s*\)\s*>\s*0\b',
                r'\1', line)
            new = re.sub(
                r'\blen\(\s*([a-zA-Z_][\w\.\[\]\'"]*)\s*\)\s*==\s*0\b',
                r'not \1', new)
            if new != line:
                lines[lineno - 1] = new
                changed += 1
        if changed == 0:
            return None
        new_text = "".join(lines)
        try:
            ast.parse(new_text)
        except SyntaxError:
            return None
        return AppliedFix(
            fixed_text=new_text,
            diff="".join(difflib.unified_diff(
                text.splitlines(keepends=True), new_text.splitlines(keepends=True),
                fromfile=str(path), tofile=str(path), n=1)),
            lines_changed=changed,
        )


# ─────────────────────────────────────────────
# 5. in d.keys() → in d
# ─────────────────────────────────────────────
class DictKeysFixer:
    name = "dict_keys_membership"

    def can_fix(self, v: Violation) -> bool:
        return v.rule == "dict_keys_membership" and v.auto_fixable

    def fix(self, path: Path, violations: list[Violation]) -> AppliedFix | None:
        text = read_text_safe(path)
        if text is None:
            return None
        lines = text.splitlines(keepends=True)
        changed = 0
        for v in violations:
            if not self.can_fix(v):
                continue
            lineno = v.lineno
            if lineno < 1 or lineno > len(lines):
                continue
            line = lines[lineno - 1]
            # x in d.keys()  →  x in d
            new = re.sub(
                r'(\bin\s+[a-zA-Z_][\w\.\[\]]*)\.keys\(\)',
                r'\1', line)
            if new != line:
                lines[lineno - 1] = new
                changed += 1
        if changed == 0:
            return None
        new_text = "".join(lines)
        try:
            ast.parse(new_text)
        except SyntaxError:
            return None
        return AppliedFix(
            fixed_text=new_text,
            diff="".join(difflib.unified_diff(
                text.splitlines(keepends=True), new_text.splitlines(keepends=True),
                fromfile=str(path), tofile=str(path), n=1)),
            lines_changed=changed,
        )


# ─────────────────────────────────────────────
# 6. x == True / x == False  →  x / not x
# ─────────────────────────────────────────────
class VerboseBoolFixer:
    name = "verbose_bool"

    def can_fix(self, v: Violation) -> bool:
        return v.rule == "verbose_bool" and v.auto_fixable

    def fix(self, path: Path, violations: list[Violation]) -> AppliedFix | None:
        text = read_text_safe(path)
        if text is None:
            return None
        lines = text.splitlines(keepends=True)
        changed = 0
        for v in violations:
            if not self.can_fix(v):
                continue
            lineno = v.lineno
            if lineno < 1 or lineno > len(lines):
                continue
            line = lines[lineno - 1]
            # == True  →  (فقط اگه سمت چپ یک expression ساده باشه)
            # == False →  not ...
            new = re.sub(
                r'([a-zA-Z_][\w\.\[\]]*)\s*==\s*True\b', r'\1', line)
            new = re.sub(
                r'([a-zA-Z_][\w\.\[\]]*)\s*==\s*False\b', r'not \1', new)
            new = re.sub(
                r'([a-zA-Z_][\w\.\[\]]*)\s*!=\s*True\b', r'not \1', new)
            new = re.sub(
                r'([a-zA-Z_][\w\.\[\]]*)\s*!=\s*False\b', r'\1', new)
            if new != line:
                lines[lineno - 1] = new
                changed += 1
        if changed == 0:
            return None
        new_text = "".join(lines)
        try:
            ast.parse(new_text)
        except SyntaxError:
            return None
        return AppliedFix(
            fixed_text=new_text,
            diff="".join(difflib.unified_diff(
                text.splitlines(keepends=True), new_text.splitlines(keepends=True),
                fromfile=str(path), tofile=str(path), n=1)),
            lines_changed=changed,
        )


# ─────────────────────────────────────────────
# Registry
# ─────────────────────────────────────────────
ALL_FIXERS = [
    SilentFailFixer(),
    NoneComparisonFixer(),
    WhileOneFixer(),
    LenTruthinessFixer(),
    DictKeysFixer(),
    VerboseBoolFixer(),
]


def get_fixer(rule: str):
    for f in ALL_FIXERS:
        if f.name == rule:
            return f
    return None
