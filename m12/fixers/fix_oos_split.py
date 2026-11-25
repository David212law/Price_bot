#!/usr/bin/env python3
"""M12 Researcher OOS fixer — adds SPLIT_PCT=0.7 to researcher.py."""
import argparse, pathlib, subprocess, sys, re, shutil

REPO = pathlib.Path("/data/data/com.termux/files/home/Price_bot")
TARGET = REPO / "m12/researcher/researcher.py"

def plan_patch():
    c = TARGET.read_text()
    if "SPLIT_PCT" in c and "oos_start_idx" in c:
        return None, "OOS already present"
    
    patches = []
    # 1. Add SPLIT_PCT constant
    if "SPLIT_PCT" not in c:
        c2 = c.replace("FEE = {", "SPLIT_PCT = 0.7  # 70% train / 30% OOS\nFEE = {", 1)
        if c2 == c: return None, "FEE = { not found"
        patches.append("SPLIT_PCT")
        c = c2
    
    # 2. Add split_idx after n = len(btc)
    if "split_idx" not in c:
        c2 = re.sub(
            r"(btc_r = label_regimes\(btc\); n = len\(btc\))",
            r"\1\n    split_idx = int(n * SPLIT_PCT)\n    print(f'TRAIN=0..{split_idx} OOS={split_idx}..{n}')",
            c, count=1
        )
        if c2 == c: return None, "label_regimes line not found"
        patches.append("split_idx")
        c = c2
    
    # 3. Add oos_start_idx param to evaluate
    if "oos_start_idx" not in c:
        c2 = re.sub(
            r"def evaluate\(symbols, btc_regimes, fee, n_btc\):",
            "def evaluate(symbols, btc_regimes, fee, n_btc, oos_start_idx=None):",
            c, count=1
        )
        if c2 == c: return None, "evaluate signature not found"
        patches.append("signature")
        c = c2
    
    # 4. Inside evaluate, skip if idx >= oos_start_idx
    if "if oos_start_idx is not None" not in c:
        c2 = re.sub(
            r"(if idx < 0 or idx >= n_btc: continue\n)(\s+r = btc_regimes\[idx\])",
            r"\1                if oos_start_idx is not None and idx >= oos_start_idx: continue\n\2",
            c, count=1
        )
        if c2 == c: return None, "idx check not found"
        patches.append("skip_logic")
        c = c2
    
    # 5. Pass split_idx from main
    if "oos_start_idx=split_idx" not in c:
        c2 = c.replace(
            "agg, n_ok = evaluate(syms, btc_r, FEE[mname], n)",
            "agg, n_ok = evaluate(syms, btc_r, FEE[mname], n, oos_start_idx=split_idx)"
        )
        if c2 == c: return None, "evaluate call not found"
        patches.append("call")
        c = c2
    
    return c, ",".join(patches)

def apply(dry_run=False):
    result, msg = plan_patch()
    if result is None: return False, msg
    bkp = TARGET.with_suffix(".py.bak")
    shutil.copy2(TARGET, bkp)
    if not dry_run: TARGET.write_text(result)
    return True, msg

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    
    if a.status:
        c = TARGET.read_text()
        print(f"File: {TARGET.relative_to(REPO)}")
        print(f"  SPLIT_PCT: {'SPLIT_PCT' in c}")
        print(f"  oos_start_idx: {'oos_start_idx' in c}")
        return 0
    
    original = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=REPO, capture_output=True, text=True).stdout.strip()
    
    if a.test:
        print(f"[test] switching to m12-lab (from {original})")
        subprocess.run(["git", "checkout", "m12-lab"], cwd=REPO, check=True)
        subprocess.run(["git", "pull", "--rebase", "origin", "m12-lab"], cwd=REPO, check=True)
    
    try:
        ok, msg = apply(dry_run=a.dry_run)
        if not ok: print(f"⏭️  {msg}"); return 0
        if a.dry_run: print(f"✅ [dry-run] would apply: {msg}"); return 0
        
        # syntax check
        r = subprocess.run([sys.executable, "-m", "py_compile", str(TARGET)],
            capture_output=True, text=True)
        if r.returncode != 0:
            print(f"❌ syntax: {r.stderr}")
            bkp = TARGET.with_suffix(".py.bak")
            shutil.copy2(bkp, TARGET); return 1
        print(f"✅ patched: {msg}")
        
        if a.test:
            subprocess.run(["git", "add", str(TARGET.relative_to(REPO))], cwd=REPO)
            subprocess.run(["git", "commit", "-m", "lab: OOS split"], cwd=REPO)
            print("✅ Committed to m12-lab")
            print("→ Review: git diff main..m12-lab m12/researcher/researcher.py")
        elif a.apply:
            subprocess.run(["git", "add", str(TARGET.relative_to(REPO))], cwd=REPO)
            subprocess.run(["git", "commit", "-m", "v68.1: researcher OOS split"], cwd=REPO)
            print("✅ Committed to main")
    finally:
        pass

if __name__ == "__main__":
    sys.exit(main())
