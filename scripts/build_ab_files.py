"""Build Conservative and Aggressive JSON files from pending."""
import json
import os

PENDING = "data/researcher_pending.json"
CONS = "data/researcher_conservative.json"
AGGR = "data/researcher_aggressive.json"

if not os.path.exists(PENDING):
    print("❌ No pending file")
    exit(1)

pending = json.load(open(PENDING))

conservative_results = {}
aggressive_results = {}

for market_name, market_data in pending.items():
    if market_data is None:
        continue
    if "predictive_conservative" not in market_data:
        print(f"⚠️ {market_name}: no predictive_conservative")
        continue
    
    base = {
        "market": market_data["market"],
        "assets": market_data["assets"],
        "days": market_data["days"],
        "oracle": market_data["oracle"],
        "bnh_btc": market_data["bnh_btc"]
    }
    
    conservative_results[market_name] = {**base, "predictive": market_data["predictive_conservative"]}
    aggressive_results[market_name] = {**base, "predictive": market_data["predictive_aggressive"]}

with open(CONS, "w") as f:
    json.dump(conservative_results, f, indent=2)
print(f"✅ Saved Conservative: {len(conservative_results)} markets, {os.path.getsize(CONS)} bytes")

with open(AGGR, "w") as f:
    json.dump(aggressive_results, f, indent=2)
print(f"✅ Saved Aggressive: {len(aggressive_results)} markets, {os.path.getsize(AGGR)} bytes")

# نمایش خلاصه
for fname, label in [(CONS, "Conservative"), (AGGR, "Aggressive")]:
    d = json.load(open(fname))
    print(f"\n--- {label} ---")
    for m in ["TMN", "USDT", "GLOBAL"]:
        if m in d:
            pred = d[m]["predictive"]
            print(f"  {m}: return={pred.get('return', 0):.1f}%, sharpe={pred.get('sharpe', 0):.2f}, dd={pred.get('dd', 0):.1f}%")
