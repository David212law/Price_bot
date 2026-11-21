"""M12 Project Manager Agent (diagnose-only for now).

Scope today: only the M12 researcher module is watched.
Future: more modules (other bots/files) plug in here.
"""
import datetime, json, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent        # m12/
REPO = ROOT.parent                                     # Price_bot/
REPORT = ROOT / "agent_report.txt"
STATE = ROOT / "agent_state.json"
NOW = datetime.datetime.now().isoformat(timespec="seconds")

# ---------------------------------------------------------------- core
def run(cmd, cwd=None, timeout=None):
    p = subprocess.run(cmd, cwd=str(cwd or ROOT), text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       timeout=timeout)
    return {"rc": p.returncode, "out": p.stdout, "err": p.stderr}

def tail(t, n=15):
    ls = (t or "").strip().splitlines()
    return "\n".join(ls[-n:]) if ls else "(empty)"

def check_exists(rel, label=None):
    p = ROOT / rel
    return {"name": label or rel, "ok": p.exists(), "path": str(p)}

# ---------------------------------------------------------------- module: m12_researcher
def module_m12_researcher():
    """Watch the M12 researcher module. Read-only. No fix."""
    checks = [
        check_exists("researcher/prefilter.py"),
        check_exists("researcher/researcher.py"),
        check_exists("researcher/verify.py"),
        check_exists("researcher/run_pipeline.py"),
        check_exists("config.json"),
        check_exists("calc.py"),
        check_exists("calc_test.py"),
    ]
    # config sanity
    cfg = ROOT / "config.json"
    detail = ""
    if cfg.exists():
        try:
            d = json.loads(cfg.read_text())
            detail = "markets=" + str(list(d.keys()))
        except Exception as e:
            detail = f"parse error: {e}"
    checks.append({"name": "config.json sanity", "ok": not detail.startswith("parse"),
                   "detail": detail})

    # quick health: compile the researcher module files
    for rel in ["researcher/prefilter.py", "researcher/researcher.py",
                "researcher/verify.py", "researcher/run_pipeline.py"]:
        r = run([sys.executable, "-m", "py_compile", str(ROOT / rel)])
        checks.append({"name": f"compile {rel}", "ok": r["rc"] == 0,
                       "err": tail(r["err"]) if r["rc"] else ""})

    return {"module": "m12_researcher", "checks": checks}

# ---------------------------------------------------------------- main
def main():
    print("=" * 62)
    print(" M12 PROJECT MANAGER AGENT  (diagnose-only)")
    print(" scope today: m12_researcher  |  started: " + NOW)
    print("=" * 62)

    modules = [module_m12_researcher]
    all_ok = True
    lines = [f"PROJECT MANAGER AGENT REPORT  ({NOW})"]
    for mod_fn in modules:
        mod = mod_fn()
        mok = all(c["ok"] for c in mod["checks"])
        all_ok = all_ok and mok
        lines.append(f"\n[MODULE] {mod['module']}  -> {'OK' if mok else 'ISSUES'}")
        for c in mod["checks"]:
            mark = "OK" if c["ok"] else "MISS"
            lines.append(f"   [{mark}] {c['name']}  {c.get('path','')}")
            if c.get("detail"): lines.append(f"          {c['detail']}")
            if c.get("err"):    lines.append(f"          {c['err']}")

    REPORT.write_text("\n".join(lines))
    print("\n".join(lines))
    print("\nreport saved ->", REPORT)
    if not all_ok:
        print("ISSUES FOUND (read-only; no auto-fix yet)")
        sys.exit(1)
    print("ALL WATCHED MODULES OK (read-only)")

if __name__ == "__main__":
    main()
