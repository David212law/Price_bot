"""Build ONE unified strategy database from ALL sources."""
import os, json, glob
from datetime import datetime

UNIFIED_DB = "data/all_strategies_unified.json"
BLACKLIST = ["M31_THRESHOLD", "M31_SMA", "M31_MOMENTUM", "M31_EMA", "M31_QUANTILE"]

def main():
    print("="*80)
    print(" BUILDING UNIFIED STRATEGY DATABASE (ALL SOURCES)")
    print("="*80)
    
    unified = {
        "built_at": datetime.now().isoformat(),
        "total": 0,
        "strategies": {},
    }
    
    # Source 1: state.json (9035 profiler strategies)
    print("\n[1] Loading state.json...")
    if os.path.exists("research_lab/logs/profiles/state.json"):
        state = json.load(open("research_lab/logs/profiles/state.json"))
        done = state.get("done", {})
        loaded = 0
        skipped_bl = 0
        skipped_no_file = 0
        skipped_short = 0
        for key, v in done.items():
            if not isinstance(v, dict): continue
            parts = key.split(":")
            if len(parts) < 4: continue
            exch, strat, h, sym = parts[0], parts[1], parts[2], parts[3]
            
            # Skip blacklist
            if any(bl in strat for bl in BLACKLIST):
                skipped_bl += 1
                continue
            
            # Find returns file — try both exact and stripped versions
            ret_file = f"research_lab/logs/profiles/returns_matrices/{exch}/{strat}_{h}_{sym}.json"
            if not os.path.exists(ret_file):
                # Try alternate path: {strat}_{sym}.json (no h)
                ret_file_alt = f"research_lab/logs/profiles/returns_matrices/{exch}/{strat}_{sym}.json"
                if os.path.exists(ret_file_alt):
                    ret_file = ret_file_alt
                else:
                    skipped_no_file += 1
                    continue
            
            try:
                rets = json.load(open(ret_file))
                if len(rets) < 60: 
                    skipped_short += 1
                    continue
                
                sid = f"{exch}::{strat}::{h}::{sym}"
                unified["strategies"][sid] = {
                    "source": "profiler",
                    "exchange": exch,
                    "strategy": strat,
                    "symbol": sym,
                    "returns": rets,
                    "sharpe_historical": v.get("validation", {}).get("sharpe_ann", 0),
                    "status": v.get("status", "unknown"),
                }
                loaded += 1
            except: pass
        
        print(f"  ✅ Loaded {loaded} from state.json")
        print(f"     Skipped: {skipped_bl} blacklist, {skipped_no_file} no file, {skipped_short} short")
    else:
        print("  ⚠️ state.json not found")
    
    # Source 2: Wallex 512 new returns (from merge)
    print("\n[2] Loading Wallex merged strategies...")
    if os.path.exists("research_lab/logs/profiles/returns_matrices/wallex"):
        loaded = 0
        for ret_file in glob.glob("research_lab/logs/profiles/returns_matrices/wallex/*.json"):
            name = os.path.basename(ret_file).replace("_WALLEX.json", "")
            try:
                rets = json.load(open(ret_file))
                if len(rets) < 60: continue
                
                sid = f"wallex::{name}::ALL"
                unified["strategies"][sid] = {
                    "source": "wallex_merged",
                    "exchange": "wallex",
                    "strategy": name,
                    "symbol": "ALL",
                    "returns": rets,
                }
                loaded += 1
            except: pass
        print(f"  ✅ Loaded {loaded} from wallex/returns_matrices")
    else:
        print("  ⚠️ wallex returns not found")
    
    # Save
    unified["total"] = len(unified["strategies"])
    os.makedirs("data", exist_ok=True)
    json.dump(unified, open(UNIFIED_DB, "w"), separators=(',', ':'))
    
    print(f"\n{'='*80}")
    print(f"✅ UNIFIED DB CREATED: {UNIFIED_DB}")
    print(f"   Total strategies: {unified['total']}")
    size_mb = os.path.getsize(UNIFIED_DB) / 1024 / 1024
    print(f"   File size: {size_mb:.1f} MB")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
