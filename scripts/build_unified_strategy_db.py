"""Build ONE unified strategy database from ALL sources. No filters, no exceptions."""
import os, json, glob
from datetime import datetime

UNIFIED_DB = "data/all_strategies_unified.json"
BLACKLIST = ["M31_THRESHOLD", "M31_SMA", "M31_MOMENTUM", "M31_EMA", "M31_QUANTILE"]

def load_returns(ret_file):
    try:
        r = json.load(open(ret_file))
        if isinstance(r, dict) and len(r) >= 60:
            return r
    except: pass
    return None

def main():
    print("="*80)
    print(" BUILDING UNIFIED STRATEGY DATABASE")
    print("="*80)
    
    unified = {"built_at": datetime.now().isoformat(), "strategies": {}}
    strats = unified["strategies"]
    
    # ═══ SOURCE 1: state.json (ALL statuses) ═══
    print("\n[1] Loading state.json (ALL statuses)...")
    state_path = "research_lab/logs/profiles/state.json"
    if os.path.exists(state_path):
        state = json.load(open(state_path))
        done = state.get("done", {})
        counts = {"loaded": 0, "blacklist": 0, "no_file": 0, "short": 0, "invalid_key": 0}
        
        for key, v in done.items():
            if not isinstance(v, dict): 
                counts["invalid_key"] += 1
                continue
            parts = key.split(":")
            if len(parts) < 4: 
                counts["invalid_key"] += 1
                continue
            
            exch, strat, h, sym = parts[0], parts[1], parts[2], parts[3]
            
            # Blacklist
            if any(bl in strat for bl in BLACKLIST):
                counts["blacklist"] += 1
                continue
            
            # Find return file
            ret_file = f"research_lab/logs/profiles/returns_matrices/{exch}/{strat}_{h}_{sym}.json"
            if not os.path.exists(ret_file):
                # Try without h
                ret_file_alt = f"research_lab/logs/profiles/returns_matrices/{exch}/{strat}_{sym}.json"
                if os.path.exists(ret_file_alt):
                    ret_file = ret_file_alt
                else:
                    counts["no_file"] += 1
                    continue
            
            rets = load_returns(ret_file)
            if not rets:
                counts["short"] += 1
                continue
            
            sid = f"{exch}::{strat}::{h}::{sym}"
            strats[sid] = {
                "source": "profiler",
                "exchange": exch,
                "strategy": strat,
                "symbol": sym,
                "returns": rets,
                "status": v.get("status", "unknown"),
                "sharpe_historical": v.get("validation", {}).get("sharpe_ann", 0),
            }
            counts["loaded"] += 1
        
        print(f"  ✅ Loaded: {counts['loaded']}")
        print(f"     Skipped: {counts['blacklist']} blacklist, {counts['no_file']} no file, {counts['short']} short, {counts['invalid_key']} invalid key")
    else:
        print("  ⚠️ state.json not found")
    
    # ═══ SOURCE 2: wallex merged strategies ═══
    print("\n[2] Loading Wallex merged...")
    wallex_dir = "research_lab/logs/profiles/returns_matrices/wallex"
    if os.path.exists(wallex_dir):
        count = 0
        for ret_file in glob.glob(f"{wallex_dir}/*.json"):
            name = os.path.basename(ret_file).replace("_WALLEX.json", "")
            rets = load_returns(ret_file)
            if not rets: continue
            
            sid = f"wallex::{name}::ALL"
            strats[sid] = {
                "source": "wallex_merged",
                "exchange": "wallex",
                "strategy": name,
                "symbol": "ALL",
                "returns": rets,
            }
            count += 1
        print(f"  ✅ Loaded: {count}")
    else:
        print("  ⚠️ wallex directory not found")
    
    # Save
    unified["total"] = len(strats)
    os.makedirs("data", exist_ok=True)
    with open(UNIFIED_DB, "w") as f:
        json.dump(unified, f, separators=(',', ':'))
    
    print(f"\n{'='*80}")
    print(f"✅ UNIFIED DB CREATED")
    print(f"   Total: {unified['total']} strategies")
    print(f"   Size: {os.path.getsize(UNIFIED_DB)/1024/1024:.1f} MB")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
