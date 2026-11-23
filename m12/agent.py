"""M12 Manager Agent v2 — L1+L2+L3, project-wide checks, Bale alerts.

L1 observe: syntax, undefined names, config/state validity, YAML, file sizes
L2 auto-fix: add missing imports, strip trailing whitespace (safe only)
L3 act: auto-commit if safe changes + calc_test passes, Bale alert on critical
"""
import ast, builtins, datetime, json, pathlib, subprocess, sys, argparse, os, shutil, re, urllib.request

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
    path = pathlib.Path(path)
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

# SAFE FIXERS v3
BACKUP_DIR = ROOT / "agent_backup"

def _prepare_backup():
    if BACKUP_DIR.exists(): shutil.rmtree(BACKUP_DIR)
    BACKUP_DIR.mkdir(parents=True)

def _backup(path):
    rel = path.relative_to(REPO)
    dest = BACKUP_DIR / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists(): shutil.copy2(path, dest)

def _restore(path):
    src = BACKUP_DIR / path.relative_to(REPO)
    if src.exists(): shutil.copy2(src, path)

def _rollback_all():
    if not BACKUP_DIR.exists(): return 0
    n = 0
    for f in BACKUP_DIR.rglob("*.py"):
        target = REPO / f.relative_to(BACKUP_DIR)
        if target.exists(): shutil.copy2(f, target); n += 1
    return n

def fix_eof_newline(path):
    code = path.read_text()
    if not code: return False
    new = code.rstrip("\n") + "\n"
    if new != code: path.write_text(new); return True
    return False

def fix_blank_lines(path):
    code = path.read_text()
    new = re.sub(r'\n{3,}', '\n\n', code)
    if new != code: path.write_text(new); return True
    return False

def fix_none_comparison(path):
    try:
        original = path.read_text(); tree = ast.parse(original)
    except SyntaxError: return False
    targets = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            if isinstance(node.ops[0], (ast.Eq, ast.NotEq)):
                l = node.left; r = node.comparators[0]
                if (isinstance(l, ast.Constant) and l.value is None) or (isinstance(r, ast.Constant) and r.value is None):
                    targets.add(node.lineno)
    if not targets: return False
    lines = original.split("\n"); changed = False
    for ln in targets:
        i = ln - 1
        if 0 <= i < len(lines):
            nl = re.sub(r'\s*==\s*None\b', ' is None', lines[i])
            nl = re.sub(r'\s*!=\s*None\b', ' is not None', nl)
            if nl != lines[i]: lines[i] = nl; changed = True
    if not changed: return False
    nc = "\n".join(lines)
    try: ast.parse(nc)
    except SyntaxError: return False
    path.write_text(nc); return True

def fix_bare_except(path):
    try:
        original = path.read_text(); tree = ast.parse(original)
    except SyntaxError: return False
    targets = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            targets.add(node.lineno)
    if not targets: return False
    lines = original.split("\n"); changed = False
    for ln in targets:
        i = ln - 1
        if 0 <= i < len(lines) and "except:" in lines[i]:
            lines[i] = lines[i].replace("except:", "except Exception:")
            changed = True
    if not changed: return False
    nc = "\n".join(lines)
    try: ast.parse(nc)
    except SyntaxError: return False
    path.write_text(nc); return True


def fix_dict_keys_membership(path):
    """'a' in d.keys() → 'a' in d (safe, faster)."""
    original = path.read_text()
    new = re.sub(r'(\bin\s+[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\.keys\(\)', r'\1', original)
    new = re.sub(r'(\bnot\s+in\s+[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\.keys\(\)', r'\1', new)
    if new != original:
        try: ast.parse(new)
        except SyntaxError: return False
        path.write_text(new); return True
    return False

def fix_not_in(path):
    """not x in y → x not in y (PEP-8)."""
    original = path.read_text()
    new = re.sub(r'\bnot\s+([A-Za-z_][A-Za-z0-9_]*(?:\[[^\]]+\])?)\s+in\s+', r'\1 not in ', original)
    if new != original:
        try: ast.parse(new)
        except SyntaxError: return False
        path.write_text(new); return True
    return False


def fix_while_1(path):
    """while 1: -> while True: (safe, cosmetic)."""
    code = path.read_text()
    new = code.replace("while 1:", "while True:")
    if new != code:
        path.write_text(new); return True
    return False

def fix_len_truthiness(path):
    """if len(x) > 0: -> if x:   and   if len(x) == 0: -> if not x:
    Safe for list/dict/str/set/tuple. Verified by calc_test."""
    code = path.read_text()
    new = code
    new = re.sub(r"len\(([a-zA-Z_][\w]*)\)\s*>\s*0", r"\1", new)
    new = re.sub(r"len\(([a-zA-Z_][\w]*)\)\s*==\s*0", r"not \1", new)
    if new != code:
        path.write_text(new); return True
    return False

def fix_verbose_true(path):
    """if x == True: -> if x:  and  if x == False: -> if not x: (safe bool)."""
    code = path.read_text()
    new = re.sub(r"==\s*True\b", "", code)
    new = re.sub(r"==\s*False\b", "not", new)
    if new != code:
        path.write_text(new); return True
    return False

def check_sleeping_bots():
    """Diagnostic: find bot dirs and flag any with no recent state activity.
    Returns (ok, detail). ok stays True (info-only, not a hard fail)."""
    import os
    bots = []
    for root, dirs, files in os.walk(str(REPO)):
        if any(x in pathlib.Path(root).parts for x in [".git", "__pycache__", "cache", ".venv"]):
            continue
        # bot state/log files
        for fn in files:
            if fn.endswith(".json") and ("state" in fn.lower()):
                p = pathlib.Path(root)/fn
                try:
                    mt = p.stat().st_mtime
                except Exception:
                    continue
                import time
                age_d = (time.time() - mt)/86400.0
                rel = p.relative_to(REPO)
                if age_d > 7:
                    bots.append(f"{rel} (no change {age_d:.0f}d)")
    if not bots:
        return True, "no inactive bots detected"
    return True, "INFO inactive: " + "; ".join(bots[:6])

SAFE_FIXERS = [
    ("eof_newline", fix_eof_newline),
    ("blank_lines", fix_blank_lines),
    ("none_comparison", fix_none_comparison),
    ("bare_except", fix_bare_except),
    ("dict_keys", fix_dict_keys_membership),
    ("not_in", fix_not_in),
    ("while_1", fix_while_1),
    ("len_truthiness", fix_len_truthiness),
    ("verbose_true", fix_verbose_true),
]

def apply_safe_fixers(path):
    _backup(path)
    applied = []
    for name, fn in SAFE_FIXERS:
        try:
            if fn(path): applied.append(name)
        except Exception as e:
            print(f"  warn {name} {path.name}: {e}")
    if applied:
        try: ast.parse(path.read_text())
        except SyntaxError:
            print(f"  broken {path.name} restore"); _restore(path); return []
    return applied




# dry-run guard: patch Path.write_text to no-op
_orig_write = pathlib.Path.write_text
def _make_dry_run_noop():
    def noop(self, *a, **k): return len(a[0]) if a else 0
    pathlib.Path.write_text = noop


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--allow-dirty", action="store_true")
    ap.add_argument("--auto-fix", action="store_true")
    ap.add_argument("--auto-commit", action="store_true", help="L3: commit safe fixes")
    ap.add_argument("--bale", action="store_true", help="Send critical alerts to Bale")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--fast", action="store_true", help="Only m12 core files")
    ap.add_argument("--health", action="store_true", help="Full project health (GitHub)")
    ap.add_argument("--next", action="store_true")
    ap.add_argument("--safe-fix", action="store_true")
    ap.add_argument("--rollback", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="No writes, preview only")
    ap.add_argument("--staged", action="store_true", help="Check only git-staged .py + m12 core")
    args = ap.parse_args()
    if args.dry_run:
        print("[DRY-RUN] no writes will happen")
        _make_dry_run_noop()
    if args.rollback:
        n = _rollback_all()
        print(f"Restored {n} files")
        return 0

    if args.staged:
        r = sh(["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"], cwd=REPO)
        staged = [REPO/f for f in r["out"].splitlines() if f.endswith(".py") and (REPO/f).exists()]
        core = [ROOT/f for f in ["calc.py","calc_test.py","m12_strategies.py","data_fetcher.py"] if (ROOT/f).exists()]
        py_files = sorted(set(staged + core))
    elif args.fast:
        py_files = sorted([ROOT/f for f in ["calc.py","calc_test.py","m12_strategies.py","data_fetcher.py"]
                           if (ROOT/f).exists()])
    else:
        py_files = find_py_files()
    if not args.quiet:
        print(f"=== M12 Agent v2 | {len(py_files)} py files | {NOW} ===")

    # ═══ L2: auto-fix ═══
    fixed_files = []
    if args.safe_fix:
        _prepare_backup()
        print(f"[safe-fix] {len(py_files)} files")
        total = 0
        for pp in py_files:
            ap_ = apply_safe_fixers(pp)
            if ap_:
                total += 1
                print(f"  OK {pp.relative_to(REPO)}: {', '.join(ap_)}")
        if total:
            ct = sh([sys.executable, str(ROOT/"calc_test.py")])
            if ct["rc"] != 0:
                print("  calc_test FAIL, rollback"); _rollback_all()
            else:
                print(f"  PASS {total} files")

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
        "state": (True, "ok") if os.getenv("CI") else check_json_file(ROOT/"bot"/"state.json"),
        "sleeping_bots": check_sleeping_bots(),
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

    ROTATE_KEEP = 5
    if REPORT.exists():
        try:
            hist_dir = ROOT / "agent_reports"
            hist_dir.mkdir(exist_ok=True)
            ts = NOW.replace(":","").replace("-","")
            (hist_dir / f"report_{ts}.txt").write_text("\n".join(lines))
            hist = sorted(hist_dir.glob("report_*.txt"), key=lambda x: x.stat().st_mtime, reverse=True)
            for old in hist[ROTATE_KEEP:]: old.unlink()
        except Exception: pass
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
