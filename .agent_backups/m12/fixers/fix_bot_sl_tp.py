#!/usr/bin/env python3
"""M12 Bot SL/TP fixer — adds missing SL/TP close loop."""
import argparse, pathlib, subprocess, sys, re, shutil, tempfile

REPO = pathlib.Path("/data/data/com.termux/files/home/Price_bot")
TARGET = REPO / "m12/bot/bot.py"

def show_status():
    if not TARGET.exists():
        print("❌ target missing"); return 1
    c = TARGET.read_text()
    has_should_close = "should_close" in c
    has_sl_tp_check = bool(re.search(r"pos\[.sl.\]\s*[<>]=?\s*cur|cur\s*[<>]=?\s*pos\[.sl.\]", c))
    print(f"File: {TARGET.relative_to(REPO)}")
    print(f"  should_close in calc: {has_should_close}")
    print(f"  SL/TP check in bot: {has_sl_tp_check}")
    return 0 if (has_should_close and has_sl_tp_check) else 2

def plan_patch():
    """Return (old_snippet, new_snippet) tuple if patch needed."""
    c = TARGET.read_text()
    # Find existing close check — is it there?
    if re.search(r"pos\[.sl.\]\s*[<>]=?\s*cur|cur\s*[<>]=?\s*pos\[.sl.\]", c):
        return None, "SL/TP check already present"
    # Find the loop over positions (close section)
    m = re.search(r"(#\s*─+\s*CLOSE.*?\n)(.*?)(#\s*─+\s*OPEN)", c, re.DOTALL | re.IGNORECASE)
    if not m:
        return None, "CLOSE/OPEN section markers not found"
    old = m.group(0)
    new = '''# ── CLOSE: check all existing positions ──
    for key in list(state["positions"].keys()):
        pos = state["positions"][key]
        market, sym = pos["market"], pos["symbol"]
        prices = markets_data.get(market, {}).get(sym, [])
        if not prices: continue
        cur = prices[-1]
        reason = should_close(pos["side"], cur, pos["sl"], pos["tp"])
        if reason:
            close_position(state, key, cur, reason)

    # ── OPEN: scan all symbols in each market ──
'''
    return old, new

def apply(target_path, dry_run=False):
    old, new = plan_patch()
    if old is None: return False, new
    c = target_path.read_text()
    # Backup
    bkp = target_path.with_suffix(".py.bak")
    shutil.copy2(target_path, bkp)
    # Apply
    patched = c.replace(old, new)
    if not dry_run:
        target_path.write_text(patched)
    return True, "patched"

def run_tests():
    r = subprocess.run([sys.executable, str(REPO/"m12/calc_test.py")], capture_output=True, text=True)
    return r.returncode == 0, r.stdout.split("\n")[-3]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--test", action="store_true", help="Apply on m12-lab branch")
    ap.add_argument("--apply", action="store_true", help="Apply on main and commit")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()

    if a.status:
        return show_status()

    # Prepare: switch branch if --test
    original_branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=REPO, capture_output=True, text=True).stdout.strip()

    if a.test:
        print(f"[test] switching to m12-lab (from {original_branch})")
        subprocess.run(["git", "checkout", "m12-lab"], cwd=REPO, check=True)
        subprocess.run(["git", "pull", "--rebase", "origin", "m12-lab"], cwd=REPO, check=True)

    try:
        # Apply patch
        ok, msg = apply(TARGET, dry_run=a.dry_run)
        if not ok:
            print(f"⏭️  {msg}"); return 0
        if a.dry_run:
            print(f"✅ [dry-run] would apply: {msg}")
            # Show planned diff
            bkp = TARGET.with_suffix(".py.bak")
            if bkp.exists(): bkp.unlink()
            return 0

        # Run tests
        t_ok, t_out = run_tests()
        print(f"Tests: {'PASS' if t_ok else 'FAIL'} — {t_out}")
        if not t_ok:
            print("❌ Rollback")
            bkp = TARGET.with_suffix(".py.bak")
            if bkp.exists(): shutil.copy2(bkp, TARGET)
            return 1

        if a.test:
            subprocess.run(["git", "add", str(TARGET.relative_to(REPO))], cwd=REPO)
            subprocess.run(["git", "commit", "-m", "lab: bot SL/TP fix"], cwd=REPO)
            print("✅ Committed to m12-lab")
            print("→ Review: git diff main..m12-lab m12/bot/bot.py")
            print("→ If OK: run with --apply after git checkout main")
        elif a.apply:
            subprocess.run(["git", "add", str(TARGET.relative_to(REPO))], cwd=REPO)
            subprocess.run(["git", "commit", "-m", "v68.0: bot SL/TP loop fixed"], cwd=REPO)
            print("✅ Committed to main")
        else:
            print("✅ Patched (uncommitted). Add --test or --apply to commit.")
    finally:
        if a.test and original_branch != "m12-lab":
            pass  # leave on lab for review

if __name__ == "__main__":
    sys.exit(main())
