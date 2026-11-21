"""M12 Manager Agent - SEPARATE supervisor.

This agent does NOT run heavy tools (researcher/verify/paper_sim).
It only:
  1. reads the repo's own reports / config / source,
  2. checks for known bug patterns,
  3. writes a FIX-SUGGESTION (with code) for anything it flags.

Real number-crunching stays in the dedicated workflows/tools.
"""
import datetime, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent
REPORT = ROOT / "agent_report.txt"
NOW = datetime.datetime.now().isoformat(timespec="seconds")

# ---- light, local-only checks (no heavy execution) ----
def check(name, ok, detail="", fix_code=""):
    return {"name": name, "ok": ok, "detail": detail, "fix": fix_code}

def compile_check(path):
    p = ROOT / path
    if not p.exists():
        return check(f"exists {path}", False, "file missing",
                     f"# create or restore {path}")
    r = subprocess.run([sys.executable, "-m", "py_compile", str(p)],
                       capture_output=True, text=True)
    return check(f"compile {path}", r.returncode == 0,
                 (r.stderr or r.stdout).strip().splitlines()[-1:] or ["ok"],
                 "# fix indentation/syntax in the reported line")

def undefined_name_check(path):
    """Scan source for 'NameError: X not defined' candidates (light)."""
    p = ROOT / path
    if not p.exists():
        return None
    src = p.read_text()
    # crude: report lines that use a bare var inside main() but look off
    issues = []
    for i, line in enumerate(src.splitlines(), 1):
        m = re.search(r"cands\.append\(\(sname", line)
        if m and "def " not in line and "cands = []" not in src:
            issues.append(i)
    if not issues:
        return None
    return check(f"undefined-name {path}", False,
                 "uses cands/sname without defining cands in this scope",
                 "# inside main(): replace cands.append(...) with cnt/best bookkeeping")

def config_crash():
    cfg = ROOT / "config.json"
    if not cfg.exists():
        return check("config.json CRASH", False, "missing",
                     "# run researcher (separate workflow) to generate config.json")
    try:
        import json
        d = json.loads(cfg.read_text())
    except Exception as e:
        return check("config.json CRASH", False, f"parse: {e}", "# fix JSON")
    parts = [f"{m}={len(d.get(m, {}).get('CRASH', {}))}" for m in ["TMN","USDT","GLOBAL"]]
    ok = all(len(d.get(m, {}).get("CRASH", {})) > 0 for m in d.keys())
    return check("config.json CRASH", ok, ", ".join(parts),
                 "# soften CRASH selection in researcher.py if entries stay 0")

def main():
    print("=" * 60)
    print(" M12 MANAGER AGENT (separate supervisor, no heavy runs)")
    print(" started: " + NOW)
    print("=" * 60)

    results = []
    for f in ["researcher/researcher.py", "researcher/prefilter.py",
              "researcher/verify.py", "researcher/run_pipeline.py",
              "calc.py", "calc_test.py"]:
        results.append(compile_check(f))
        u = undefined_name_check(f)
        if u: results.append(u)
    results.append(config_crash())

    lines = [f"MANAGER AGENT REPORT (separate supervisor)  ({NOW})"]
    for r in results:
        mark = "PASS" if r["ok"] else "FLAG"
        lines.append(f"   [{mark}] {r['name']}")
        if r["detail"]: lines.append(f"          {r['detail']}")
        if r["fix"]:    lines.append(f"          FIX-CODE: {r['fix']}")
    REPORT.write_text("\n".join(lines))
    print("\n".join(lines))
    print("\nreport saved ->", REPORT)
    if any(not r["ok"] for r in results):
        print("FLAGGED items (supervisor only; apply fixes manually or in L2)")
        sys.exit(1)
    print("ALL CHECKS PASSED (supervisor)")

if __name__ == "__main__":
    main()
