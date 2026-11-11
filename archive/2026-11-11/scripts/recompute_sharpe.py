"""Recompute Sharpe for all 9035 profiled strategies from returns_matrices."""
import os, json, math

STATE = "research_lab/logs/profiles/state.json"
RETURNS_DIR = "research_lab/logs/profiles/returns_matrices"

def calc_sharpe(rets_dict):
    """Sharpe from daily returns dict {date: ret_pct}."""
    if not rets_dict or len(rets_dict) < 30: return 0.0
    vals = list(rets_dict.values())
    n = len(vals)
    m = sum(vals) / n
    var = sum((r - m)**2 for r in vals) / n
    std = var ** 0.5
    if std == 0: return 0.0
    # tpy: trades per year
    dates = sorted(rets_dict.keys())
    from datetime import datetime
    try:
        span = (datetime.strptime(dates[-1], "%Y-%m-%d") - 
                datetime.strptime(dates[0], "%Y-%m-%d")).days
        tpy = n / (span / 365.25) if span > 0 else n
    except:
        tpy = n
    return (m / std) * (tpy ** 0.5)

def main():
    if not os.path.exists(STATE):
        print("❌ state.json not found")
        return
    state = json.load(open(STATE))
    done = state.get("done", {})
    print(f"Total: {len(done)}")
    
    updated = 0
    skipped = 0
    for key, v in done.items():
        if not isinstance(v, dict): continue
        parts = key.split(":")
        if len(parts) < 4: skipped += 1; continue
        exch, strat, h, sym = parts[0], parts[1], parts[2], parts[3]
        ret_file = f"{RETURNS_DIR}/{exch}/{strat}_{h}_{sym}.json"
        if not os.path.exists(ret_file): skipped += 1; continue
        try:
            rets = json.load(open(ret_file))
            sr = calc_sharpe(rets)
            if "validation" not in v: v["validation"] = {}
            v["validation"]["sharpe_ann"] = round(sr, 4)
            updated += 1
        except: skipped += 1
    
    json.dump(state, open(STATE, "w"), indent=2)
    print(f"✅ Updated Sharpe for {updated} strategies, skipped {skipped}")

if __name__ == "__main__":
    main()
