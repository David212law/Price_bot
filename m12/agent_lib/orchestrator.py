"""
Orchestrator — هماهنگ‌کننده کل pipeline با safety.

قواعد امنیتی:
  1. فایل‌های PROTECTED هرگز fix نمی‌شن
  2. بعد از هر batch، agent_self_test اجرا می‌شه
  3. اگه self_test fail شد، کل batch rollback می‌شه
  4. diff هر تغییر قبل از apply چاپ می‌شه (اگه --show-diff)
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from agent_lib.core import (
    REPO, RunReport, Violation, FixResult,
    make_run_id, now_iso, iter_python_files, git_dirty_count,
    get_runtime_info, Timer,
)
from agent_lib.detectors.ast_detector import ALL_DETECTORS
from agent_lib.fixers.ast_fixer import get_fixer
from agent_lib.verifiers.chain import run_all_verifiers, verify_self_test
from agent_lib.safety import should_skip, PROTECTED_FILES, PROTECTED_FILES


MAX_FIXES_PER_RUN = 100
BACKUP_DIR = REPO / ".agent_backups"
REPORT_DIR = REPO / "m12" / "agent" / "reports"


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def backup_file(path: Path) -> Path | None:
    try:
        rel = path.relative_to(REPO)
    except ValueError:
        return None
    dst = BACKUP_DIR / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dst)
    return dst


def restore_file(path: Path) -> bool:
    try:
        rel = path.relative_to(REPO)
    except ValueError:
        return False
    src = BACKUP_DIR / rel
    if not src.exists():
        return False
    shutil.copy2(src, path)
    return True


def group_by_file(violations: list[Violation]) -> dict[Path, list[Violation]]:
    out: dict[Path, list[Violation]] = {}
    for v in violations:
        out.setdefault(Path(v.file), []).append(v)
    return out


def group_by_rule(violations: list[Violation]) -> dict[str, list[Violation]]:
    out: dict[str, list[Violation]] = {}
    for v in violations:
        out.setdefault(v.rule, []).append(v)
    return out


def _apply_one_file(path_obj: Path, rule: str, vs: list[Violation],
                     fixer, dry_run: bool, show_diff: bool) -> tuple[bool, FixResult]:
    """اعمال fix روی یک فایل. برمی‌گردونه: (applied?, FixResult)"""
    t = Timer()
    with t:
        # ─── safety check
        skip, reason = should_skip(path_obj)
        if skip:
            return False, FixResult(
                file=str(path_obj), rule=rule, applied=False,
                reason=f"skip: {reason}",
                duration_ms=round(t.ms, 2),
            )

        backup_file(path_obj)
        result = fixer.fix(path_obj, vs)
        if result is None:
            return False, FixResult(
                file=str(path_obj), rule=rule, applied=False,
                reason="no change",
                duration_ms=round(t.ms, 2),
            )

        # ─── verify syntax + compile
        ver = run_all_verifiers(
            path_obj, result.fixed_text, result.diff,
            run_self_test=False,
        )
        if not ver.passed:
            restore_file(path_obj)
            return False, FixResult(
                file=str(path_obj), rule=rule, applied=False,
                reason="verify: " + " | ".join(m for _, ok, m in ver.checks if not ok),
                verifier_passed=False,
                duration_ms=round(t.ms, 2),
            )

        # ─── show diff
        if show_diff:
            print(f"\n  ── DIFF {path_obj.relative_to(REPO)} ({rule}) ──")
            print(result.diff)
            print(f"  ── END DIFF ──\n")

        # ─── apply or dry-run
        if not dry_run:
            path_obj.write_text(result.fixed_text)
            return True, FixResult(
                file=str(path_obj), rule=rule, applied=True,
                reason="ok", verifier_passed=True,
                diff_lines=result.lines_changed,
                duration_ms=round(t.ms, 2),
            )
        else:
            return True, FixResult(
                file=str(path_obj), rule=rule, applied=False,
                reason="dry-run: would apply", verifier_passed=True,
                diff_lines=result.lines_changed,
                duration_ms=round(t.ms, 2),
            )


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
def run(
    path: Path | None = None,
    rules: list[str] | None = None,
    dry_run: bool = True,
    max_fixes: int = MAX_FIXES_PER_RUN,
    run_self_test: bool = True,
    include_archive: bool = False,
    show_diff: bool = False,
) -> RunReport:
    rt = get_runtime_info()
    report = RunReport(
        run_id=make_run_id(),
        started_at=now_iso(),
        git_dirty_files=git_dirty_count(),
        **rt,
    )

    # ─── فایل‌ها
    if path:
        files = [path] if path.is_file() else list(path.rglob("*.py"))
        if not include_archive:
            files = [f for f in files if "archive" not in f.parts]
    else:
        files = iter_python_files()

    # ─── detector ها
    if rules:
        detectors = [d for d in ALL_DETECTORS if d.name in rules]
        missing = set(rules) - {d.name for d in detectors}
        if missing:
            print(f"❌ unknown rules: {missing}")
            return report
    else:
        detectors = ALL_DETECTORS

    mode = "DRY-RUN" if dry_run else "APPLY"
    print(f"🔍 Scanning {len(files)} files with {len(detectors)} detectors ({mode})")
    print(f"   run_id: {report.run_id}")
    print(f"   protected files: {len(PROTECTED_FILES)}")
    print()

    # ─── detect
    all_violations: list[Violation] = []
    for d in detectors:
        vs, stats = d.run(files)
        all_violations.extend(vs)
        report.detectors.append(stats)
        print(f"   {stats.name:22s}  files={stats.files_scanned:4d}  "
              f"violations={stats.violations:3d}  {stats.duration_ms:7.1f}ms")

    report.violations = all_violations
    if not all_violations:
        print("\n✅ No violations found.")
        report.finished_at = now_iso()
        return report

    # ─── process
    print()
    print(f"🛠  Processing {len(all_violations)} violations...")
    by_rule = group_by_rule(all_violations)
    applied_count = 0
    rejected_count = 0
    skipped_count = 0
    batch_backups: list[Path] = []  # فایل‌هایی که در این batch تغییر کردن

    for rule, violations in sorted(by_rule.items()):
        fixer = get_fixer(rule)
        if fixer is None:
            skipped_count += len(violations)
            print(f"  ⏭  {rule}: no fixer (needs_human, {len(violations)})")
            for v in violations:
                report.fixes.append(FixResult(
                    file=v.file, rule=rule, applied=False,
                    reason="no fixer",
                ))
            continue

        by_file = group_by_file(violations)
        for path_obj, vs in by_file.items():
            if applied_count >= max_fixes:
                print(f"  ⚠  max_fixes ({max_fixes}) reached")
                break

            # ─── safety check before apply
            skip, reason = should_skip(path_obj)
            if skip:
                skipped_count += len(vs)
                print(f"  🛡  {rule} {path_obj.relative_to(REPO)}: SKIP ({reason})")
                for v in vs:
                    report.fixes.append(FixResult(
                        file=v.file, rule=rule, applied=False,
                        reason=f"skip: {reason}",
                    ))
                continue

            ok, fr = _apply_one_file(path_obj, rule, vs, fixer,
                                      dry_run=dry_run, show_diff=show_diff)
            report.fixes.append(fr)
            if ok:
                applied_count += 1
                if not dry_run:
                    batch_backups.append(path_obj)
                icon = "✅" if not dry_run else "🔍"
                print(f"  {icon} {rule} {path_obj.relative_to(REPO)}  "
                      f"(+{fr.diff_lines} lines)")
            elif fr.reason.startswith("verify"):
                rejected_count += 1
                print(f"  ❌ {rule} {path_obj.relative_to(REPO)}: {fr.reason}")
            elif fr.reason.startswith("skip"):
                skipped_count += 1
                print(f"  🛡  {rule} {path_obj.relative_to(REPO)}: {fr.reason}")
            else:
                print(f"  ⏭  {rule} {path_obj.relative_to(REPO)}: {fr.reason}")

    # ─── self-test بعد از batch
    if run_self_test and not dry_run and applied_count > 0:
        print()
        print("🧪 Running agent_self_test.py after batch...")
        ok, msg = verify_self_test()
        if ok:
            print(f"   ✅ {msg}")
        else:
            print(f"   ❌ {msg}")
            print(f"   🔄 Rolling back {len(batch_backups)} files...")
            for p in batch_backups:
                restore_file(p)
            applied_count = 0
            print(f"   ⚠  All fixes in this batch rolled back due to self-test failure")

    # ─── خلاصه
    report.finished_at = now_iso()
    report.decisions = {
        "total_violations": len(all_violations),
        "auto_fixable": sum(1 for v in all_violations if v.auto_fixable),
        "needs_human": sum(1 for v in all_violations if not v.auto_fixable),
        "fixes_applied": applied_count if not dry_run else 0,
        "fixes_would_apply": applied_count if dry_run else 0,
        "fixes_rejected": rejected_count,
        "fixes_skipped": skipped_count,
    }
    return report


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Agent orchestrator")
    ap.add_argument("--path", default=None)
    ap.add_argument("--rules", default=None)
    ap.add_argument("--apply", action="store_true",
                    help="apply fixes (default is dry-run)")
    ap.add_argument("--max-fixes", type=int, default=MAX_FIXES_PER_RUN)
    ap.add_argument("--no-self-test", action="store_true")
    ap.add_argument("--include-archive", action="store_true")
    ap.add_argument("--show-diff", action="store_true",
                    help="نمایش diff هر تغییر")
    ap.add_argument("--json", default=None)
    ap.add_argument("--save-report", action="store_true")
    args = ap.parse_args(argv)

    rules = args.rules.split(",") if args.rules else None
    dry_run = not args.apply

    report = run(
        path=Path(args.path) if args.path else None,
        rules=rules,
        dry_run=dry_run,
        max_fixes=args.max_fixes,
        run_self_test=not args.no_self_test,
        include_archive=args.include_archive,
        show_diff=args.show_diff,
    )

    print()
    print("=" * 72)
    for k, v in report.decisions.items():
        print(f"  {k:24s} {v}")
    print("=" * 72)

    if args.json:
        out = Path(args.json)
        report.save(out)
        print(f"💾 {out}")

    if args.save_report:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        out = REPORT_DIR / f"report_{report.run_id}.json"
        report.save(out)
        print(f"💾 {out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
