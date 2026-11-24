#!/usr/bin/env python3
import argparse
import pathlib
import subprocess
import sys
from typing import Dict, List, Tuple


def repo_root() -> pathlib.Path:
    # Avoid __file__ (static fixer flags it as undefined)
    p = pathlib.Path.cwd().resolve()

    # If already in repo root
    if (p / "m12").exists():
        return p

    # Walk up until we find a folder that looks like the repo
    for parent in p.parents:
        if (parent / "m12").exists():
            return parent
    return p


def _run_subprocess(
    *,
    name: str,
    root: str,
    target: str,
    extra_env: Dict[str, str],
    timeout: int,
) -> Tuple[int, str]:
    env = dict(extra_env)
    env["SMOKE_ROOT"] = root
    env["PYTHONPATH"] = env.get("PYTHONPATH", root)

    code = r"""
import importlib, importlib.util, sys, os
root = os.environ["SMOKE_ROOT"]

if root and (not sys.path or sys.path[0] != root):
    sys.path.insert(0, root)

print("LAB_DEBUG cwd=", os.getcwd())
print("LAB_DEBUG root=", root)
print("LAB_DEBUG sys.path_head=", sys.path[:8])

try:
    importlib.import_module("m12")
    print("IMPORT_m12=OK")
except Exception as e:
    print("IMPORT_m12=FAIL", repr(e))
    raise

target = os.environ["LAB_TARGET"]
spec = importlib.util.spec_from_file_location("lab_target_mod", target)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

print("IMPORT_TARGET=OK")
"""

    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=root,
        env={**env, "LAB_TARGET": target},
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    joined = "\n".join([x for x in [out, err] if x])
    return proc.returncode, joined


def main():
    ap = argparse.ArgumentParser(description="M12 Agent Lab (manual-only, import-only)")
    ap.add_argument(
        "--target",
        default="exchanges/aster/m11_aster_allocator.py",
        help="Target .py path relative to repo root",
    )
    ap.add_argument(
        "--strategies",
        default="all",
        choices=["all", "py_path_only", "clean_sys_path"],
        help="Which import-path strategies to test",
    )
    ap.add_argument("--report", default="m12/agent_lab_report.txt")
    ap.add_argument("--timeout", type=int, default=12)
    args = ap.parse_args()

    R = repo_root()
    target_path = (R / args.target).resolve()
    if not target_path.exists():
        raise SystemExit(f"Target not found: {target_path}")

    root = str(R)
    target = str(target_path)

    strategies: List[Tuple[str, Dict[str, str]]] = []
    if args.strategies == "all":
        strategies = [
            ("py_path_only", {"PYTHONPATH": root}),
            ("clean_sys_path", {"PYTHONPATH": root, "PYTHONNOUSERSITE": "1"}),
        ]
    elif args.strategies == "py_path_only":
        strategies = [("py_path_only", {"PYTHONPATH": root})]
    else:
        strategies = [("clean_sys_path", {"PYTHONPATH": root, "PYTHONNOUSERSITE": "1"})]

    lines = []
    lines.append("=== M12 AGENT LAB (import-only) ===")
    lines.append(f"repo={root}")
    lines.append(f"target={target}")
    lines.append(f"timeout={args.timeout}")
    lines.append("")

    any_fail = False
    for name, extra_env in strategies:
        lines.append(f"--- STRATEGY {name} ---")
        rc, report = _run_subprocess(
            name=name,
            root=root,
            target=target,
            extra_env=extra_env,
            timeout=args.timeout,
        )
        lines.append(f"rc={rc}")
        lines.append(report)
        lines.append("")
        if rc != 0:
            any_fail = True

    lines.append("=== SUMMARY ===")
    lines.append("result=" + ("FAIL" if any_fail else "PASS"))

    out_path = R / args.report
    out_path.write_text("\n".join(lines))
    print(out_path)
    print("DONE result=", "FAIL" if any_fail else "PASS")


if __name__ == "__main__":
    main()
