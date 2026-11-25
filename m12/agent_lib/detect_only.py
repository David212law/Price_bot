"""
detect_only.py — فقط detectors رو اجرا می‌کنه و گزارش می‌ده.
هیچ فایلی تغییر نمی‌ده.

Usage:
    python -m agent.detect_only                 # همه فایل‌ها
    python -m agent.detect_only --fast          # فقط m12 core
    python -m agent.detect_only --json out.json # ذخیره JSON
    python -m agent.detect_only --summary       # فقط خلاصه
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agent_lib.core import (
    REPO, RunReport, make_run_id, now_iso, iter_python_files,
    git_dirty_count, get_runtime_info,
)
from agent_lib.detectors.ast_detector import run_all, ALL_DETECTORS


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true",
                    help="فقط m12 core (سریع)")
    ap.add_argument("--path", default=None,
                    help="مسیر خاص (پیش‌فرض: کل repo)")
    ap.add_argument("--json", default=None,
                    help="ذخیره گزارش JSON در این مسیر")
    ap.add_argument("--summary", action="store_true",
                    help="فقط خلاصه نشون بده")
    ap.add_argument("--rule", default=None,
                    help="فقط این rule")
    args = ap.parse_args(argv)

    # ─── انتخاب فایل‌ها
    if args.path:
        files = list(Path(args.path).rglob("*.py"))
    elif args.fast:
        files = [p for p in iter_python_files()
                 if "m12" in p.parts and "cache" not in p.parts]
    else:
        files = iter_python_files()

    # ─── فیلتر rule
    if args.rule:
        detectors = [d for d in ALL_DETECTORS if d.name == args.rule]
        if not detectors:
            print(f"❌ rule '{args.rule}' not found. موجود: "
                  + ", ".join(d.name for d in ALL_DETECTORS))
            return 1
    else:
        detectors = ALL_DETECTORS

    # ─── اجرا
    rt = get_runtime_info()
    report = RunReport(
        run_id=make_run_id(),
        started_at=now_iso(),
        git_dirty_files=git_dirty_count(),
        **rt,
    )

    print(f"🔍 Scanning {len(files)} files with {len(detectors)} detectors...")
    print(f"   run_id: {report.run_id}")
    print(f"   python: {rt['python_version']}   platform: {rt['platform']}")
    print()

    violations = []
    for d in detectors:
        v, s = d.run(files)
        violations.extend(v)
        report.detectors.append(s)
        print(f"   {s.name:22s}  files={s.files_scanned:4d}  "
              f"violations={s.violations:3d}  errors={s.errors}  "
              f"{s.duration_ms:7.1f}ms")

    report.violations = violations
    report.finished_at = now_iso()

    # ─── آمار decisions (اولیه: بر اساس auto_fixable)
    auto_fixable = sum(1 for v in violations if v.auto_fixable)
    needs_human = len(violations) - auto_fixable
    report.decisions = {
        "auto_fixable": auto_fixable,
        "needs_human": needs_human,
        "total": len(violations),
    }

    # ─── نمایش
    print()
    print("=" * 72)
    print(f"  TOTAL: {len(violations)} violations")
    print(f"    auto_fixable: {auto_fixable}")
    print(f"    needs_human:  {needs_human}")
    print("=" * 72)

    if not args.summary and violations:
        print()
        by_rule: dict[str, list] = {}
        for v in violations:
            by_rule.setdefault(v.rule, []).append(v)
        for rule in sorted(by_rule):
            vs = by_rule[rule]
            print(f"\n▸ {rule} ({len(vs)})")
            for v in vs[:10]:
                rel = Path(v.file).relative_to(REPO) if Path(v.file).is_relative_to(REPO) else v.file
                print(f"   {rel}:{v.lineno}  {v.context[:80]}")
            if len(vs) > 10:
                print(f"   ... و {len(vs)-10} مورد دیگر")

    # ─── ذخیره JSON
    if args.json:
        out = Path(args.json)
        report.save(out)
        print(f"\n💾 JSON: {out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
