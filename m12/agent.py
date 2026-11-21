"""M12 Manager Agent — separate supervisor using precise detection tools.

The agent does not compute strategy metrics itself. It uses lightweight
tools (py_compile + a scope-aware AST undefined-name detector) to inspect
the repo and reports PASS/FLAG with a fix suggestion.

L1 (active): observe + suggest.
L2 (ready) : auto-apply known-pattern fixes, then re-verify.
"""
import ast, builtins, datetime, json, pathlib, subprocess, sys, argparse

ROOT = pathlib.Path(__file__).resolve().parent
REPO = ROOT.parent
REPORT = ROOT / "agent_report.txt"
NOW = datetime.datetime.now().isoformat(timespec="seconds")
BUILTINS = set(dir(builtins))

FILES = [
    "researcher/researcher.py", "researcher/prefilter.py",
    "researcher/verify.py", "researcher/run_pipeline.py",
    "calc.py", "calc_test.py",
]

# ---------------------------------------------------------------- tools
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

# ---- scope-aware undefined-name detector ----
def _target_names(n):
    if isinstance(n, ast.Name):
        return {n.id}
    ids = set()
    for c in ast.iter_child_nodes(n):
        ids |= _target_names(c)
    return ids

def _local_names(node):
    names = {a.arg for a in node.args.args + node.args.kwonlyargs}
    if node.args.vararg: names.add(node.args.vararg.arg)
    if node.args.kwarg:  names.add(node.args.kwarg.arg)
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            names.add(n.id)
        if isinstance(n, ast.comprehension):
            names |= _target_names(n.target)
        if isinstance(n, ast.Lambda):
            for a in n.args.args: names.add(a.arg)
            if n.args.vararg: names.add(n.args.vararg.arg)
            if n.args.kwarg:  names.add(n.args.kwarg.arg)
        # function-level imports
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                names.add((a.asname or a.name).split(".")[0])
    return names

def module_defs(tree):
    names = set()
    for n in ast.iter_child_nodes(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(n.name)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names: names.add(a.asname or a.name.split(".")[0])
        elif isinstance(n, ast.Assign):
            for t in n.targets: names |= _target_names(t)
    return names

def undefined_names(path):
    try:
        tree = ast.parse(pathlib.Path(path).read_text())
    except SyntaxError:
        return []
    mod = module_defs(tree)
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        local = _local_names(node)
        for n in ast.walk(node):
            if (isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
                    and n.id not in local and n.id not in mod
                    and n.id not in BUILTINS):
                out.append((node.name, n.id, n.lineno))
    return out

# ---------------------------------------------------------------- checks
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

# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--allow-dirty", action="store_true", help="Ignore uncommitted git files")
    args = ap.parse_args()
    print("=" * 62)
    print(" M12 MANAGER AGENT  [L1 observer / L2 ready]  started: " + NOW)
    print("=" * 62)

    lines = [f"MANAGER AGENT REPORT ({NOW})"]
    all_ok = True

    for f in FILES:
        c = py_compile(f)
        if not c["ok"]:
            all_ok = False
            lines.append(f"   [FLAG] syntax {f}: {c['why']}")
        for func, name, line in undefined_names(str(ROOT / f)):
            all_ok = False
            lines.append(f"   [FLAG] undefined-name {f}:{line} — {func}() uses '{name}' not in scope")
            lines.append(f"          FIX: define '{name}' in {func}() before use")

    checks = [config_crash()]
    if not args.allow_dirty:
        checks.append(git_tracked_dirty())
    for name, ok, why in checks:
        if not ok:
            all_ok = False
            lines.append(f"   [FLAG] {name}: {why}")

    REPORT.write_text("\n".join(lines))
    print("\n".join(lines))
    print("\nreport saved ->", REPORT)
    if not all_ok:
        print("\nFLAGGED items (L1 observes; L2 fixers ready)")
        sys.exit(1)
    print("\nALL CHECKS PASSED (L1 supervisor)")

if __name__ == "__main__":
    main()
