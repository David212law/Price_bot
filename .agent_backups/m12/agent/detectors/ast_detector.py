"""
AST-based detectors — فقط detect، هیچ‌وقت تغییر نمی‌ده.
هر detector کلاس جدا داره، قابل تست مستقل.
"""
from __future__ import annotations

import ast
from pathlib import Path

from agent.core import (
    BaseDetector, Violation, node_line, node_col, source_line,
)


# ─────────────────────────────────────────────
# 1. Silent fail: except: pass  (فقط except خالی)
# ─────────────────────────────────────────────
class SilentFailDetector(BaseDetector):
    name = "silent_fail"

    def detect(self, path: Path, tree: ast.AST) -> list[Violation]:
        out: list[Violation] = []
        src = ""
        try:
            src = path.read_text(encoding="utf-8")
        except OSError:
            pass
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            # فقط except: بدون type  +  body = [Pass]
            if node.type is not None:
                continue
            if len(node.body) != 1 or not isinstance(node.body[0], ast.Pass):
                continue
            out.append(Violation(
                file=str(path), lineno=node_line(node), col=node_col(node),
                rule=self.name, severity="warning",
                message="`except: pass` — خطا بی‌صدا نادیده گرفته می‌شه",
                auto_fixable=True,
                context=source_line(src, node_line(node)),
                detector=self.name,
            ))
        return out


# ─────────────────────────────────────────────
# 2. Bare except: except:  (بدون pass — فقط detect)
# ─────────────────────────────────────────────
class BareExceptDetector(BaseDetector):
    name = "bare_except"

    def detect(self, path: Path, tree: ast.AST) -> list[Violation]:
        out: list[Violation] = []
        src = ""
        try:
            src = path.read_text(encoding="utf-8")
        except OSError:
            pass
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            if node.type is not None:
                continue
            # اگه silent_fail هم بود، دوبار گزارش نکن
            if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                continue
            out.append(Violation(
                file=str(path), lineno=node_line(node), col=node_col(node),
                rule=self.name, severity="error",
                message="`except:` بدون نوع — KeyboardInterrupt هم گرفته می‌شه",
                auto_fixable=False,  # fix خودکار امن نیست
                context=source_line(src, node_line(node)),
                detector=self.name,
            ))
        return out


# ─────────────────────────────────────────────
# 3. x == None  →  x is None
# ─────────────────────────────────────────────
class NoneComparisonDetector(BaseDetector):
    name = "none_comparison"

    def detect(self, path: Path, tree: ast.AST) -> list[Violation]:
        out: list[Violation] = []
        src = ""
        try:
            src = path.read_text(encoding="utf-8")
        except OSError:
            pass
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            for op in node.ops:
                if isinstance(op, (ast.Eq, ast.NotEq)):
                    comparators = node.comparators
                    if any(isinstance(c, ast.Constant) and c.value is None for c in comparators):
                        out.append(Violation(
                            file=str(path), lineno=node_line(node), col=node_col(node),
                            rule=self.name, severity="info",
                            message="`== None` / `!= None` — بهتره `is None` / `is not None`",
                            auto_fixable=True,
                            context=source_line(src, node_line(node)),
                            detector=self.name,
                        ))
                        break
        return out


# ─────────────────────────────────────────────
# 4. x == True / x == False
# ─────────────────────────────────────────────
class VerboseBoolDetector(BaseDetector):
    name = "verbose_bool"

    def detect(self, path: Path, tree: ast.AST) -> list[Violation]:
        out: list[Violation] = []
        src = ""
        try:
            src = path.read_text(encoding="utf-8")
        except OSError:
            pass
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            for c in node.comparators:
                if isinstance(c, ast.Constant) and c.value in (True, False):
                    out.append(Violation(
                        file=str(path), lineno=node_line(node), col=node_col(node),
                        rule=self.name, severity="info",
                        message=f"`== {c.value}` — می‌تونه ساده‌تر باشه",
                        auto_fixable=True,
                        context=source_line(src, node_line(node)),
                        detector=self.name,
                    ))
                    break
        return out


# ─────────────────────────────────────────────
# 5. len(x) > 0  →  x
# ─────────────────────────────────────────────
class LenTruthinessDetector(BaseDetector):
    name = "len_truthiness"

    def detect(self, path: Path, tree: ast.AST) -> list[Violation]:
        out: list[Violation] = []
        src = ""
        try:
            src = path.read_text(encoding="utf-8")
        except OSError:
            pass
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            # len(x) > 0  یا  len(x) == 0
            if not (isinstance(node.left, ast.Call)
                    and isinstance(node.left.func, ast.Name)
                    and node.left.func.id == "len"):
                continue
            if not (len(node.comparators) == 1
                    and isinstance(node.comparators[0], ast.Constant)
                    and node.comparators[0].value == 0
                    and isinstance(node.ops[0], (ast.Gt, ast.Eq))):
                continue
            out.append(Violation(
                file=str(path), lineno=node_line(node), col=node_col(node),
                rule=self.name, severity="info",
                message="`len(x) > 0` — می‌شه فقط `x`",
                auto_fixable=True,
                context=source_line(src, node_line(node)),
                detector=self.name,
            ))
        return out


# ─────────────────────────────────────────────
# 6. while 1  →  while True
# ─────────────────────────────────────────────
class WhileOneDetector(BaseDetector):
    name = "while_one"

    def detect(self, path: Path, tree: ast.AST) -> list[Violation]:
        out: list[Violation] = []
        src = ""
        try:
            src = path.read_text(encoding="utf-8")
        except OSError:
            pass
        for node in ast.walk(tree):
            if not isinstance(node, ast.While):
                continue
            if (isinstance(node.test, ast.Constant)
                    and node.test.value == 1
                    and not isinstance(node.test.value, bool)):
                out.append(Violation(
                    file=str(path), lineno=node_line(node), col=node_col(node),
                    rule=self.name, severity="info",
                    message="`while 1` — بهتره `while True`",
                    auto_fixable=True,
                    context=source_line(src, node_line(node)),
                    detector=self.name,
                ))
        return out


# ─────────────────────────────────────────────
# 7. dict.keys() membership  →  in dict
# ─────────────────────────────────────────────
class DictKeysMembershipDetector(BaseDetector):
    name = "dict_keys_membership"

    def detect(self, path: Path, tree: ast.AST) -> list[Violation]:
        out: list[Violation] = []
        src = ""
        try:
            src = path.read_text(encoding="utf-8")
        except OSError:
            pass
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            if not isinstance(node.ops[0], (ast.In, ast.NotIn)):
                continue
            right = node.comparators[0]
            if (isinstance(right, ast.Call)
                    and isinstance(right.func, ast.Attribute)
                    and right.func.attr == "keys"
                    and len(right.args) == 0):
                out.append(Violation(
                    file=str(path), lineno=node_line(node), col=node_col(node),
                    rule=self.name, severity="info",
                    message="`in d.keys()` — می‌شه فقط `in d`",
                    auto_fixable=True,
                    context=source_line(src, node_line(node)),
                    detector=self.name,
                ))
        return out


# ─────────────────────────────────────────────
# Registry
# ─────────────────────────────────────────────
ALL_DETECTORS: list[BaseDetector] = [
    SilentFailDetector(),
    BareExceptDetector(),
    NoneComparisonDetector(),
    VerboseBoolDetector(),
    LenTruthinessDetector(),
    WhileOneDetector(),
    DictKeysMembershipDetector(),
]


def run_all(files: list[Path]) -> tuple[list[Violation], list]:
    """اجرای همه detectors. خروجی: (violations, stats)"""
    all_violations: list[Violation] = []
    all_stats = []
    for d in ALL_DETECTORS:
        v, s = d.run(files)
        all_violations.extend(v)
        all_stats.append(s)
    return all_violations, all_stats
