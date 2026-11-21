"""M12 Manager Agent v2 — L1+L2+L3, project-wide checks, Bale alerts.

L1 observe: syntax, undefined names, config/state validity, YAML, file sizes
L2 auto-fix: add missing imports, strip trailing whitespace (safe only)
L3 act: auto-commit if safe changes + calc_test passes, Bale alert on critical
"""
import ast, builtins, datetime, json, pathlib, subprocess, sys, argparse, os, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
REPO = ROOT.parent
REPORT = ROOT / "agent_report.txt"
NOW = datetime.datetime.now().isoformat(timespec="seconds")
BUILTINS = set(dir(builtins))

# ─── Scope: پروژه کامل، با skip پوشه‌های حجیم/سنتی ───
SKIP_DIRS = {"__pycache__", ".git", "cache", "node_modules", "archive", ".venv", "venv"}
SKIP_FILES_PREFIX = {"agent"}  # agent.py خودش

def find_py_files():
    out = []
    for p in REPO.rglob("*.py"):
        if any(s in p.parts for s in SKIP_DIRS): continue
        if p.name.startswith("agent"): continue
        out.append(p)
    return sorted(out)

KNOWN_MODULES = {"random":"import random","statistics":"import statistics",
    "math":"import math","re":"import re","json":"import json","os":"import os",
    "sys":"import sys","csv":"import csv","subprocess":"import subprocess",
    "hashlib":"import hashlib","argparse":"import argparse","pathlib":"import pathlib",
    "urllib":"import urllib.request","time":"import time"}

def sh(cmd, cwd=None):
    p = subprocess.run(cmd, cwd=str(cwd or ROOT), capture_output=True, text=True)
    return {"rc": p.returncode, "out": p.stdout, "err": p.stderr}

def py_compile(path):
    r = sh([sys.executable, "-m", "py_compile", str(path)])
    return r["rc"] == 0, ((r["err"] or r["out"]).strip().splitlines()[-1:] or [""])[0]

def _target_names(n):
    if isinstance(n, ast.Name): return {n.id}
    ids = set()
    for c in ast.iter_child_nodes(n): ids |= _target_names(c)
    return ids

def collect_all_names(tree):
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
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:
        return []
    bound = collect_all_names(tree)
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)): continue
        for n in ast.walk(node):
            if (isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
                    and n.id not in bound and n.id not in BUILTINS):
                out.append((node.name, n.id, n.lineno))
    return out

def fix_missing_imports(path):
    if not path.exists(): return []
    code = path.read_text(); seen = []
    for func, name, line in undefined_names(path):
        if name in KNOWN_MODULES and name not in seen:
            if f"import {name}" in code: continue
            lines = code.splitlines(keepends=True)
            insert_at = 1 if (lines and lines[0].startswith("#!")) else 0
            if insert_at < len(lines):
                ls = lines[insert_at].lstrip()
                if ls.startswith('"""') or ls.startswith("'''"):
                    delim = ls[:3]
                    for j in range(insert_at+1, min(insert_at+30, len(lines))):
                        if delim in lines[j]: insert_at = j + 1; break
            code = "".join(lines[:insert_at]) + KNOWN_MODULES[name] + "\n" + "".join(lines[insert_at:])
            path.write_text(code); seen.append(name)
    return seen

def fix_trailing_whitespace(path):
    code = path.read_text()
    new = "\n".join(line.rstrip() for line in code.split("\n"))
    if new != code:
        path.write_text(new); return True
    return False

def check_json_file(path, required_keys=None):
    if not path.exists(): return False, f"missing {path.name}"
    try: data = json.loads(path.read_text())
    except Exception as e: return False, f"parse: {e}"
    if required_keys:
        missing = [k for k in required_keys if k not in data]
        if missing: return False, f"missing keys: {missing}"
    return True, "ok"

def check_config_crash():
    ok, _ = check_json_file(ROOT/"config.json")
    if not ok: return False, "config invalid"
    d = json.loads((ROOT/"config.json").read_text())
    parts, all_ok = [], True
    for m in ["TMN","USDT","GLOBAL"]:
        n = len(d.get(m, {}).get("CRASH", {}))
        parts.append(f"{m}={n}")
        if n == 0: all_ok = False
    return all_ok, ", ".join(parts)

def check_workflows():
    wf_dir = REPO/".github"/"workflows"
    if not wf_dir.exists(): return True, "no workflows"
    bad = []
    for f in wf_dir.glob("*.yml"):
        try:
            txt = f.read_text()
            if "jobs:" not in txt: bad.append(f.name)
        except: bad.append(f.name)
    return (not bad), (f"invalid: {bad}" if bad else f"{len(list(wf_dir.glob('*.yml')))} files ok")

def check_large_files(threshold=1500):
    big = [str(p.relative_to(REPO)) for p in find_py_files() if len(p.read_text().splitlines()) > threshold]
    return (not big), (f"large: {big[:3]}" if big else "ok")

def check_bale_env():
    return bool(os.environ.get("BALE_BOT_TOKEN")), "BALE_BOT_TOKEN" if os.environ.get("BALE_BOT_TOKEN") else "not set (skip alerts)"

def git_dirty():
    r = sh(["git", "status", "--short"], cwd=REPO)
    return [l for l in r["out"].splitlines() if l.strip() and not l.startswith("?? ")]

def send_bale(msg):
    tok = os.environ.get("BALE_BOT_TOKEN",""); ch = os.environ.get("BALE_CHAT_ID","")
    if not tok or not ch: print(f"[BALE-SKIP] {msg}"); return
    try:
        req = urllib.request.Request(f"https://tapi.bale.ai/bot{tok}/sendMessage",
            data=json.dumps({"chat_id": ch, "text": msg}).encode(),
            headers={"Content-Type":"application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception as e: print(f"[BALE-ERR] {e}")



# ═══════════════ Health & Next-Action ═══════════════
HEALTH_FILE = ROOT / "agent_health.json"

def _health_load():
    if HEALTH_FILE.exists():
        try: return json.loads(HEALTH_FILE.read_text())
        except: pass
    return {"config_history": [], "last_check": None, "known_issues": []}

def _health_save(d): HEALTH_FILE.write_text(json.dumps(d, indent=2))

def _within_hours(iso, h=24):
    try:
        t = datetime.datetime.fromisoformat(iso)
        return (datetime.datetime.now() - t).total_seconds() < h*3600
    except: return False

def check_project_health():
    """Detect known project issues (config instability, dead bots, etc)."""
    issues = []
    warns = []

    # 1. Config stability
    cfg = ROOT / "config.json"
    if cfg.exists():
        import hashlib
        h = hashlib.md5(cfg.read_bytes()).hexdigest()[:8]
        hist = _health_load()
        hist["config_history"].append({"hash": h, "time": NOW})
        hist["config_history"] = hist["config_history"][-20:]
        _health_save(hist)
        recent = [e for e in hist["config_history"] if _within_hours(e["time"], 24)]
        unique = len(set(e["hash"] for e in recent))
        if unique >= 3:
            issues.append(f"CONFIG UNSTABLE: {unique} hashes in 24h (overfit risk)")
        elif unique == 2:
            warns.append(f"config changed once in 24h")

    # 2. Calc tests
    ct = sh([sys.executable, str(ROOT/"calc_test.py")])
    if ct["rc"] != 0:
        issues.append("CALC TESTS FAILED")

    # 3. Bot state health
    st = ROOT/"bot"/"state.json"
    if st.exists():
        try:
            d = json.loads(st.read_text())
            eq = d.get("equity", 0)
            if eq < 9500:
                issues.append(f"BOT EQUITY LOW: ${eq:.0f}")
            hist = d.get("history", [])
            recent = [h for h in hist if _within_hours(
                datetime.datetime.fromtimestamp(h["time"]/1000).isoformat() if isinstance(h.get("time"), (int,float))
                else str(h.get("time","")), 48)]
            if len(hist) > 0 and len(recent) == 0:
                warns.append("no trades in 48h (regime=BEAR?)")
        except: pass

    # 4. M31 silent check
    m31_file = REPO/"exchanges"/"aster"/"state"/"m11_aster_paper_state.json"
    if m31_file.exists():
        try:
            d = json.loads(m31_file.read_text())
            if len(d.get("history", [])) == 0:
                warns.append("M31 never traded (legacy dead)")
        except: pass

    return issues, warns

def suggest_next(issues, warns):
    """Suggest prioritized next actions."""
    actions = []
    if any("CONFIG UNSTABLE" in i for i in issues):
        actions.append("P0: Freeze config + add OOS split (in-sample overfit)")
    if any("CALC TESTS FAILED" in i for i in issues):
        actions.append("P0: Fix calc.py before anything")
    if any("BOT EQUITY LOW" in i for i in issues):
        actions.append("P0: Kill switch check — reduce max_pos or pause")
    if any("M31 never traded" in w for w in warns):
        actions.append("P1: M31 dead — extract capital or implement Delta-Neutral")
    if not actions:
        actions.append("OK: project healthy, monitor 48h")
    return actions

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--allow-dirty", action="store_true")
    ap.add_argument("--auto-fix", action="store_true")
    ap.add_argument("--auto-commit", action="store_true", help="L3: commit safe fixes")
    ap.add_argument("--bale", action="store_true", help="Send critical alerts to Bale")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--fast", action="store_true", help="Only m12 core files")
    ap.add_argument("--health", action="store_true", help="Full project health (GitHub)")
    ap.add_argument("--next", action="store_true", help="Suggest next action")
    args = ap.parse_args()

    if args.fast:
        py_files = sorted([ROOT/f for f in ["calc.py","calc_test.py","m12_strategies.py","data_fetcher.py"]
                           if (ROOT/f).exists()])
    else:
        py_files = find_py_files()
    if not args.quiet:
        print(f"=== M12 Agent v2 | {len(py_files)} py files | {NOW} ===")

    # ═══ L2: auto-fix ═══
    fixed_files = []
    if args.auto_fix:
        for p in py_files:
            imports_added = fix_missing_imports(p)
            if imports_added: fixed_files.append(f"{p.name}: +{imports_added}")
            if fix_trailing_whitespace(p): fixed_files.append(f"{p.name}: ws")

    # ═══ L1: checks ═══
    flags = []
    syntax_errors = []
    for p in py_files:
        ok, why = py_compile(p)
        if not ok:
            syntax_errors.append(f"{p.relative_to(REPO)}: {why}")
            flags.append(("CRITICAL", f"syntax {p.relative_to(REPO)}: {why}"))
        for func, name, line in undefined_names(p):
            flags.append(("HIGH", f"{p.relative_to(REPO)}:{line} {func}() → '{name}' undefined"))
    
    checks = {
        "config_crash": check_config_crash(),
        "workflows": check_workflows(),
        "large_files": check_large_files(),
        "state": check_json_file(ROOT/"bot"/"state.json"),
    }
    for name, (ok, why) in checks.items():
        if not ok: flags.append(("HIGH" if name=="config_crash" else "LOW", f"{name}: {why}"))

    dirty = git_dirty()
    if dirty and not args.allow_dirty:
        flags.append(("INFO", f"git dirty: {len(dirty)} files"))

    # ═══ Report ═══
    lines = [f"AGENT REPORT ({NOW})", f"Files: {len(py_files)}", ""]
    if fixed_files:
        lines.append("AUTO-FIXED:")
        for f in fixed_files: lines.append(f"  ✓ {f}")
        lines.append("")
    if flags:
        lines.append("FLAGS:")
        for sev, msg in flags: lines.append(f"  [{sev}] {msg}")
    else:
        lines.append("ALL CHECKS PASSED")

    if args.health or args.next:
        issues, warns = check_project_health()
        lines.append("")
        lines.append("PROJECT HEALTH:")
        if issues:
            for i in issues: lines.append(f"  🚨 {i}")
            flags += [("CRITICAL", i) for i in issues]
        if warns:
            for w in warns: lines.append(f"  ⚠️  {w}")
        if not issues and not warns:
            lines.append("  ✅ healthy")
        if args.next:
            lines.append("")
            lines.append("NEXT ACTIONS:")
            for a in suggest_next(issues, warns): lines.append(f"  → {a}")

    REPORT.write_text("\n".join(lines))
    if not args.quiet: print("\n".join(lines))

    # ═══ Bale for critical ═══
    if args.bale:
        critical = [f for sev, f in flags if sev == "CRITICAL"]
        if critical:
            send_bale(f"🚨 M12 Agent: {len(critical)} critical\n" + "\n".join(critical[:3]))

    # ═══ L3: auto-commit ═══
    has_critical = any(sev == "CRITICAL" for sev, _ in flags)
    if args.auto_commit and fixed_files and not has_critical:
        # sanity: calc test
        ct = sh([sys.executable, str(ROOT/"calc_test.py")])
        if ct["rc"] != 0:
            print("❌ calc_test failed — no auto-commit")
            return 1
        # only commit py fixes
        sh(["git", "add", "-u", "*.py"], cwd=REPO)
        stat = sh(["git", "diff", "--cached", "--stat"], cwd=REPO)
        if stat["out"].strip():
            sh(["git", "commit", "-m", f"auto(agent): {len(fixed_files)} files fixed"], cwd=REPO)
            print(f"✅ auto-committed {len(fixed_files)} files")

    return 1 if has_critical or any(sev == "HIGH" for sev, _ in flags) else 0

if __name__ == "__main__":
    sys.exit(main())
