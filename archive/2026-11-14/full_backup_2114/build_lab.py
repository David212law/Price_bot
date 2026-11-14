"""Build Lab JSON from Lab pending (Conservative stays frozen at v28.7)."""
import json
import os

PENDING = "data/researcher_lab_pending.json"
AGGR = "data/researcher_lab.json"

if not os.path.exists(PENDING):
    print("❌ No pending file")
    exit(1)

pending = json.load(open(PENDING))
aggressive_results = {}

for market_name, market_data in pending.items():
    if market_data is None:
        continue
    # Try predictive_aggressive first, then predictive
    pred = market_data.get("predictive_aggressive") or market_data.get("predictive")
    if not pred:
        print(f"⚠️ {market_name}: no predictive data")
        continue
    
    base = {
        "market": market_data["market"],
        "assets": market_data["assets"],
        "days": market_data["days"],
        "oracle": market_data["oracle"],
        "bnh_btc": market_data["bnh_btc"]
    }
    aggressive_results[market_name] = {**base, "predictive": pred}

with open(AGGR, "w") as f:
    json.dump(aggressive_results, f, indent=2)
print(f"✅ Saved Aggressive: {len(aggressive_results)} markets, {os.path.getsize(AGGR)} bytes")

print("\n--- Aggressive Results ---")
for m in ["TMN", "USDT", "GLOBAL"]:
    if m in aggressive_results:
        p = aggressive_results[m]["predictive"]
        print(f"  {m}: return={p.get('return', 0):.1f}%, sharpe={p.get('sharpe', 0):.2f}, dd={p.get('dd', 0):.1f}%")
