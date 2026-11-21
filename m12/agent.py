"""M12 Manager Agent — L1 observer + L2 auto-fix (loose scope mode)."""
import ast, builtins, datetime, json, pathlib, subprocess, sys, argparse

ROOT = pathlib.Path(__file__).resolve().parent
REPO = ROOT.parent
REPORT = ROOT / "agent_report.txt"
NOW = datetime.datetime.now().isoformat(timespec="seconds")
BUILTINS = set(dir(builtins))

FILES = sorted(
    str(p.relative_to(ROOT))
    for p in ROOT.rglob("*.py")
    if "__pycache__" not in str(p)
    and "cache" not in p.parts
    and not p.name.startswith("agent")
)

KNOWN_MODULES = {
    "random": "import random", "statistics": "import statistics",
    "math": "import math", "re": "import re", "json": "import json",
    "os": "import os", "sys": "import sys", "csv": "import csv",
    "subprocess": "import subprocess", "hashlib": "import hashlib",
    "argparse": "import argparse", "pathlib": "import pathlib",
    "urllib": "import urllib.request",
}

def sh(cmd, cwd=None):
    p = subprocess.run(cmd, cwd=str(cwd or ROOT), capture_output=True, text=True)
    return {"rc": p.returncode, "out": p.stdout, "err": p.stderr}

def py_compile(path):
    p = ROOT / path
    if not p.exists():
        return {"ok": False, "why": "missing file"}
    r = sh([sys.executable, "-m", "py_compile", str(p)])
    return {"ok": r["rc"] == 0,
            "why": (r["err"] or r["out"]).strip().splitlines()[-1:] if r["rc"] else ""}

def _target_names(n):
    if isinstance(n, ast.Name):
        return {n.id}
    ids = set()
    for c in ast.iter_child_nodes(n):
        ids |= _target_names(c)
    return ids

def collect_all_names(tree):
    """Loose scope: all names bound anywhere in the file."""
    names = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(n.name)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names: names.add((a.asname or a.name).split(".")[0])
        elif isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            names.add(n.id)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            names.add(n.name)
        elif isinstance(n, ast.withitem) and n.optional_vars:
            names |= _target_names(n.optional_vars)
        elif isinstance(n, ast.arg):
            names.add(n.arg)
        elif isinstance(n, ast.comprehension):
            names |= _target_names(n.target)
    return names

def undefined_names(path):
    """Loose detection: flag names used-but-never-bound anywhere in the file."""
    try:
        tree = ast.parse(pathlib.Path(path).read_text())
    except SyntaxError:
        return []
    all_bound = collect_all_names(tree)
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for n in ast.walk(node):
            if (isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
                    and n.id not in all_bound
                    and n.id not in BUILTINS):
                out.append((node.name, n.id, n.lineno))
    return out

def auto_fix_missing_imports(path):
    p = ROOT / path
    if not p.exists(): return []
    code = p.read_text()
    seen = set()
    for func, name, line in undefined_names(str(p)):
        if name in KNOWN_MODULES and name not in seen:
            if f"import {name}" in code: continue
            lines = code.splitlines(keepends=True)
            insert_at = 0
            if lines and lines[0].startswith("#!"): insert_at = 1
            if insert_at < len(lines):
                ls = lines[insert_at].lstrip()
                if ls.startswith('"""') or ls.startswith("'''"):
                    delim = ls[:3]
                    for j in range(insert_at+1, min(insert_at+30, len(lines))):
                        if delim in lines[j]:
                            insert_at = j + 1
                            break
            code = "".join(lines[:insert_at]) + KNOWN_MODULES[name] + "\n" + "".join(lines[insert_at:])
            p.write_text(code)
            seen.add(name)
    return list(seen)

def config_crash():
    cfg = ROOT / "config.json"
    if not cfg.exists():
        return ("config.json CRASH", False, "missing config.json")
    try:
        d = json.loads(cfg.read_text())
    except Exception as e:
        return ("config.json CRASH", False, f"JSON parse: {e}")
    parts = [f"{m}={len(d.get(m, {}).get('CRASH', {}))}" for m in ["TMN","USDT","GLOBAL"]]
    ok = all(len(d.get(m, {}).get("CRASH", {})) > 0 for m in d.keys())
    return ("config.json CRASH", ok, ", ".join(parts))

def git_tracked_dirty():
    r = sh(["git", "status", "--short"], cwd=REPO)
    dirty = [l for l in r["out"].splitlines() if l.strip() and not l.startswith("?? ")]
    return ("git tracked-state", not dirty, (", ".join(dirty) if dirty else "clean"))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--allow-dirty", action="store_true")
    ap.add_argument("--auto-fix", action="store_true")
    args = ap.parse_args()

    print("=" * 62)
    print(" M12 MANAGER AGENT  started: " + NOW)
    print("=" * 62)

    if args.auto_fix:
        print("[L2] auto-fix enabled")
        for f in FILES:
            fixed = auto_fix_missing_imports(f)
            for fx in fixed: print(f"  FIXED: added '{fx}' in {f}")

    lines = [f"MANAGER AGENT REPORT ({NOW})"]
    all_ok = True
    for f in FILES:
        c = py_compile(f)
        if not c["ok"]:
            all_ok = False
            lines.append(f"   [FLAG] syntax {f}: {c['why']}")
        for func, name, line in undefined_names(str(ROOT / f)):
            all_ok = False
            lines.append(f"   [FLAG] undefined-name {f}:{line} — {func}() uses '{name}'")
    checks = [config_crash()]
    if not args.allow_dirty:
        checks.append(git_tracked_dirty())
    for name, ok, why in checks:
        if not ok:
            all_ok = False
            lines.append(f"   [FLAG] {name}: {why}")

    REPORT.write_text("\n".join(lines))
    print("\n".join(lines))

    if not all_ok:
        print("\nFLAGGED — run with --auto-fix to try L2 fixes")
        sys.exit(1)
    print("\nALL CHECKS PASSED")

if __name__ == "__main__":
    main()
