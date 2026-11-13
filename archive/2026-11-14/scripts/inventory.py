"""MASTER INVENTORY: Everything we have (data, strategies, tests, exchanges)."""
import json, os, glob
from collections import Counter

print("="*90)
print(" MASTER INVENTORY — PRICE_BOT")
print("="*90)

# ═══════════════════════════════════════════════════════════════
# PART 1: DATA ASSETS
# ═══════════════════════════════════════════════════════════════
print("\n" + "="*90)
print(" PART 1: DATA ASSETS (what data do we have?)")
print("="*90)

data_files = sorted(glob.glob("data/*.json"))
print(f"\n{'File':<40} {'Size':>8} {'Assets':>8} {'Days':>6} {'Range'}")
print("-"*90)

data_inventory = {}
for f in data_files:
    try:
        size_kb = os.path.getsize(f) / 1024
        name = os.path.basename(f)
        
        # Skip state/result files
        if any(k in name for k in ['state', 'kill_switch', 'results', 'pending', 'aggressive']):
            continue
        
        d = json.load(open(f))
        if isinstance(d, dict):
            sample_key = list(d.keys())[0] if d else None
            sample_val = d.get(sample_key) if sample_key else None
            
            if isinstance(sample_val, dict):
                # dict of dicts (prices)
                assets = len(d)
                all_dates = set()
                for v in d.values():
                    if isinstance(v, dict):
                        all_dates.update(v.keys())
                if all_dates:
                    dates = sorted(all_dates)
                    data_inventory[name] = {
                        "type": "price_data",
                        "assets": assets,
                        "days": len(dates),
                        "start": dates[0],
                        "end": dates[-1]
                    }
                    print(f"{name:<40} {size_kb:>6.0f}K {assets:>8} {len(dates):>6} {dates[0]} → {dates[-1]}")
            elif isinstance(sample_val, (int, float)):
                dates = sorted(d.keys())
                data_inventory[name] = {
                    "type": "time_series",
                    "days": len(dates),
                    "start": dates[0],
                    "end": dates[-1]
                }
                print(f"{name:<40} {size_kb:>6.0f}K {'-':>8} {len(dates):>6} {dates[0]} → {dates[-1]}")
    except:
        pass

# ═══════════════════════════════════════════════════════════════
# PART 2: STRATEGIES
# ═══════════════════════════════════════════════════════════════
print("\n" + "="*90)
print(" PART 2: STRATEGIES (what strategies do we have?)")
print("="*90)

# 2.1: Returns matrices
print("\n[2.1] Returns Matrices (backtested strategies):")
exchanges = ["wallex", "hyperliquid", "aster", "kucoin"]
for exch in exchanges:
    path = f"research_lab/logs/profiles/returns_matrices/{exch}"
    if os.path.exists(path):
        files = glob.glob(f"{path}/*.json")
        print(f"  {exch:<15}: {len(files):>4} files")

# 2.2: Unified DB
print("\n[2.2] Unified Strategy DB:")
if os.path.exists("data/all_strategies_unified.json"):
    d = json.load(open("data/all_strategies_unified.json"))
    strategies = d.get("strategies", {})
    print(f"  Total: {len(strategies)}")
    
    # By exchange
    by_exch = Counter()
    by_status = Counter()
    for k, v in strategies.items():
        if isinstance(v, dict):
            by_exch[v.get("exchange", "?")] += 1
            by_status[v.get("status", "?")] += 1
    print(f"  By exchange: {dict(by_exch)}")
    print(f"  By status: {dict(by_status)}")

# 2.3: Profiler state
print("\n[2.3] Profiler State:")
if os.path.exists("research_lab/logs/profiles/state.json"):
    d = json.load(open("research_lab/logs/profiles/state.json"))
    done = d.get("done", {})
    print(f"  Total: {len(done)}")
    statuses = Counter()
    for k, v in done.items():
        if isinstance(v, dict):
            statuses[v.get("status", "?")] += 1
        else:
            statuses["non-dict"] += 1
    print(f"  Statuses: {dict(statuses)}")

# 2.4: High-freq bank
print("\n[2.4] High-Frequency Bank:")
if os.path.exists("data/high_freq_strategies.json"):
    d = json.load(open("data/high_freq_strategies.json"))
    print(f"  Total: {len(d)}")

# 2.5: build_strategies (in code)
print("\n[2.5] build_strategies (in Researcher):")
with open("scripts/researcher_predictive.py") as f:
    code = f.read()

mom_count = code.count("mom_")
brk_count = code.count("break")
bb_count = code.count("bb")
rsi_count = code.count("rsi")
pairs_count = code.count("pairs_")
archived_count = code.count("mom_nd_") + code.count("break_n_") + code.count("ma_cross_") + code.count("rsi_mr_")

print(f"  Strategy mentions in code:")
print(f"    mom: {mom_count}")
print(f"    break: {brk_count}")
print(f"    bb: {bb_count}")
print(f"    rsi: {rsi_count}")
print(f"    pairs: {pairs_count}")
print(f"    archived (mom_nd, break_n, ma_cross, rsi_mr): {archived_count}")

# ═══════════════════════════════════════════════════════════════
# PART 3: TESTS
# ═══════════════════════════════════════════════════════════════
print("\n" + "="*90)
print(" PART 3: TESTS (what tests do we have?)")
print("="*90)

# Active
print("\n[3.1] Active Tests (scripts/):")
test_files = glob.glob("scripts/test_*.py") + glob.glob("scripts/walk_forward*.py") + glob.glob("scripts/audit_*.py")
for f in sorted(test_files):
    size = os.path.getsize(f) / 1024
    print(f"  {os.path.basename(f):<45} {size:>6.0f}K")

# Archive
print("\n[3.2] Archived Tests:")
archived_tests = glob.glob("archive/**/test_*.py", recursive=True) + glob.glob("archive/**/walk_forward*.py", recursive=True)
for f in sorted(archived_tests):
    print(f"  {os.path.basename(f)}")

# Results
print("\n[3.3] Test Results (data/):")
result_files = glob.glob("data/*results*.json") + glob.glob("data/*walk_forward*.json")
for f in sorted(result_files):
    size = os.path.getsize(f) / 1024
    print(f"  {os.path.basename(f):<45} {size:>6.0f}K")

# ═══════════════════════════════════════════════════════════════
# PART 4: EXCHANGES (live state)
# ═══════════════════════════════════════════════════════════════
print("\n" + "="*90)
print(" PART 4: EXCHANGES (what's running?)")
print("="*90)

for exch_dir in ["wallex", "hyperliquid", "aster", "kucoin"]:
    path = f"exchanges/{exch_dir}"
    if os.path.exists(path):
        states = glob.glob(f"{path}/state/*.json")
        print(f"  {exch_dir:<15}: {len(states)} state files")

# ═══════════════════════════════════════════════════════════════
# PART 5: COVERAGE — WHAT'S MISSING
# ═══════════════════════════════════════════════════════════════
print("\n" + "="*90)
print(" PART 5: COVERAGE — what do we have vs what's missing?")
print("="*90)

coverage = [
    ("BTC/TMN ۴ سال", "data/btctmn_5y.json" if os.path.exists("data/btctmn_5y.json") else "❌", "✅" if os.path.exists("data/btctmn_5y.json") else "❌"),
    ("Altcoins/TMN ۲.۲ سال", "data/wallex_tmn_all.json", "✅"),
    ("Altcoins/USDT ۲.۲ سال", "data/wallex_usdt_all.json", "✅"),
    ("GLOBAL ۵ سال", "data/crypto_5y_usd.json", "✅"),
    ("Bear 2022 Binance", "data/crypto_2022_bear.json" if os.path.exists("data/crypto_2022_bear.json") else "❌", "✅" if os.path.exists("data/crypto_2022_bear.json") else "❌"),
    ("Iran USD/IRR ۱۵ سال", "data/usd_irr_tgju.json", "✅"),
    ("Unified strategies", "data/all_strategies_unified.json", "✅"),
    ("High-freq bank", "data/high_freq_strategies.json", "✅"),
    ("Returns matrices", "research_lab/logs/profiles/returns_matrices/", "✅"),
    ("Tests (active)", "scripts/test_*.py", "✅"),
    ("Walk-Forward", "scripts/walk_forward_v36.py" if os.path.exists("scripts/walk_forward_v36.py") else "❌", "✅" if os.path.exists("scripts/walk_forward_v36.py") else "❌"),
    ("Audit data", "scripts/audit_data_pure.py" if os.path.exists("scripts/audit_data_pure.py") else "❌", "✅" if os.path.exists("scripts/audit_data_pure.py") else "❌"),
]

print(f"\n{'Item':<30} {'Path':<45} {'Status':<8}")
print("-"*90)
for item, path, status in coverage:
    print(f"{item:<30} {path:<45} {status:<8}")

# ═══════════════════════════════════════════════════════════════
# PART 6: WHAT'S MISSING
# ═══════════════════════════════════════════════════════════════
print("\n" + "="*90)
print(" PART 6: WHAT WE'RE MISSING (gaps)")
print("="*90)

gaps = []

# Check bear 2022 in Wallex data
if os.path.exists("data/wallex_tmn_all.json"):
    d = json.load(open("data/wallex_tmn_all.json"))
    sample = list(d.values())[0]
    dates = sorted(sample.keys())
    if dates[0] > "2022-12-31":
        gaps.append("❌ Wallex TMN/Altcoins: No 2022 bear data (starts " + dates[0] + ")")

# Check if Binance fetch needed
if not os.path.exists("data/crypto_2022_bear.json"):
    gaps.append("❌ Binance 2022 bear (altcoins) missing")
else:
    gaps.append("✅ Binance 2022 bear exists (crypto_2022_bear.json)")

# Check if BTC/TMN 4yr used
if os.path.exists("data/btctmn_5y.json"):
    gaps.append("✅ BTC/TMN 4yr exists — BUT not used in regime detection!")
else:
    gaps.append("❌ BTC/TMN 4yr missing")

# Check if pairs trading exists
if "pairs_" in open("scripts/researcher_predictive.py").read():
    gaps.append("✅ Pairs Trading implemented")
else:
    gaps.append("❌ Pairs Trading not implemented")

# Check if 15-regime is used
if "detect_regime_15" in open("scripts/researcher_predictive.py").read():
    gaps.append("✅ 15-regime detection implemented")
else:
    gaps.append("❌ 15-regime not implemented")

# Check if regime thresholds are fixed
with open("scripts/researcher_predictive.py") as f:
    code = f.read()
if "v < 0.4" in code and "v >= 0.7" in code:
    gaps.append("✅ Regime thresholds fixed (0.4/0.7)")
else:
    gaps.append("❌ Regime thresholds still old (1.0/2.0)")

for g in gaps:
    print(f"  {g}")

print("\n" + "="*90)
print(" END OF INVENTORY")
print("="*90)
