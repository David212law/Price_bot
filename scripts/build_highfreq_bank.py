"""Build a bank of high-frequency strategies from existing returns."""
import json
import os
import glob

WALLEX_DIR = "research_lab/logs/profiles/returns_matrices/wallex"
OUTPUT = "data/high_freq_strategies.json"
MIN_TRADES = 30

high_freq = {}

for fpath in glob.glob(f"{WALLEX_DIR}/*_WALLEX.json"):
    fname = os.path.basename(fpath).replace("_WALLEX.json", "")
    try:
        rets = json.load(open(fpath))
        if len(rets) < 60:
            continue
        trades = sum(1 for v in rets.values() if abs(v) > 0.001)
        if trades >= MIN_TRADES:
            high_freq[fname] = {
                "file": os.path.basename(fpath),
                "trades": trades,
                "avg_daily_return": sum(rets.values()) / len(rets)
            }
    except:
        pass

os.makedirs("data", exist_ok=True)
with open(OUTPUT, "w") as f:
    json.dump(high_freq, f, indent=2)

print(f"✅ Found {len(high_freq)} high-frequency strategies (>= {MIN_TRADES} trades)")
print(f"   Saved to {OUTPUT}")
