"""
Run Experiment — اجرای آزمایشی fixer ها روی sandbox.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from agent_lib.core import (
    REPO, RunReport, Violation, FixResult,
    make_run_id, now_iso, get_runtime_info,
)
from agent_lib.detectors.ast_detector import ALL_DETECTORS
from agent_lib.fixers.ast_fixer import get_fixer
from agent_lib.verifiers.chain import run_all_verifiers
from agent_lib.safety import should_skip
from agent_test.sandbox import make_sandbox, cleanup_sandbox


def run_experiment(
    rules: list[str],
    apply: bool = False,
    keep_sandbox: bool = False,
    max_fixes: int = 50,
) -> RunReport:
    rt = get_runtime_info()
    report = RunReport(
        run_id=make_run_id(),
        started_at=now_iso(),
        **rt,
    )

    sandbox = make_sandbox(
        dest=Path(os.environ.get("TMPDIR", "/tmp")) / f"pb_exp_{report.run_id}"
    )
    print()

    files = sorted(sandbox.rglob("*.py"))
    print(f"🔍 Scanning {len(files)} files in sandbox")
    print()

    detectors = [d for d in ALL_DETECTORS if d.name in rules]
    missing = set(rules) - {d.name for d in detectors}
    if missing:
        print(f"❌ unknown rules: {missing}")
        return report

    all_violations: list[Violation] = []
    for d in detectors:
        vs, stats = d.run(files)
        all_violations.extend(vs)
        report.detectors.append(stats)
        print(f"   {stats.name:22s}  files={stats.files_scanned:4d}  "
              f"violations={stats.violations:3d}")

    report.violations = all_violations

    if apply and all_violations:
        print()
        print(f"🛠  Applying fixes to sandbox...")
        by_rule: dict[str, list[Violation]] = {}
        for v in all_violations:
            by_rule.setdefault(v.rule, []).append(v)

        applied = 0
        for rule, violations in sorted(by_rule.items()):
            fixer = get_fixer(rule)
            if fixer is None:
                print(f"  ⏭  {rule}: no fixer")
                continue

            by_file: dict[Path, list[Violation]] = {}
            for v in violations:
                try:
                    rel = Path(v.file).relative_to(REPO)
                except ValueError:
                    continue
                by_file.setdefault(rel, []).append(v)

            for rel_path, vs in by_file.items():
                if applied >= max_fixes:
                    break
                sandbox_path = sandbox / rel_path
                if not sandbox_path.exists():
                    continue
                skip, reason = should_skip(sandbox_path)
                if skip:
                    print(f"  🛡  {rule} {rel_path}: SKIP ({reason})")
                    continue

                for v in vs:
                    v.file = str(sandbox_path)

                result = fixer.fix(sandbox_path, vs)
                if result is None:
                    continue

                ver = run_all_verifiers(
                    sandbox_path, result.fixed_text, result.diff,
                    run_self_test=False,
                )
                if not ver.passed:
                    print(f"  ❌ {rule} {rel_path}: verify failed")
                    continue

                sandbox_path.write_text(result.fixed_text)
                applied += 1
                print(f"  ✅ {rule} {rel_path}  (+{result.lines_changed})")

        # self-test در sandbox
        print()
        print("🧪 Running agent_self_test.py in sandbox...")
        st = sandbox / "m12" / "agent_self_test.py"
        if st.exists():
            import subprocess
            r = subprocess.run(
                [sys.executable, str(st)],
                cwd=str(st.parent),
                capture_output=True, text=True, timeout=60,
                env={**os.environ, "PYTHONPATH": str(sandbox / "m12")},
            )
            if r.returncode == 0:
                print(f"   ✅ self-test PASS")
            else:
                print(f"   ❌ self-test FAILED")
                print(f"   stdout: {r.stdout[-400:]}")
                print(f"   stderr: {r.stderr[-400:]}")
        else:
            print(f"   ⚠  self_test.py not found")

    report.finished_at = now_iso()
    report.decisions = {
        "total_violations": len(all_violations),
        "mode": "APPLY" if apply else "DRY-RUN",
        "sandbox": str(sandbox),
    }

    if not keep_sandbox:
        print()
        cleanup_sandbox(sandbox)
    else:
        print(f"\n💾 Sandbox kept at: {sandbox}")

    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules", required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--max-fixes", type=int, default=50)
    args = ap.parse_args(argv)

    report = run_experiment(
        rules=args.rules.split(","),
        apply=args.apply,
        keep_sandbox=args.keep,
        max_fixes=args.max_fixes,
    )

    print()
    print("=" * 72)
    for k, v in report.decisions.items():
        print(f"  {k:24s} {v}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
