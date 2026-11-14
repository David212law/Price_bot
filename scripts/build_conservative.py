"""Build Conservative Best JSON from conservative_pending (for Wallex Conservative bot)."""
import json
import os

PENDING = "data/researcher_conservative_pending.json"
OUTPUT = "data/researcher_conservative_best.json"

if not os.path.exists(PENDING):
    print("❌ No conservative_pending file")
    exit(1)

pending = json.load(open(PENDING))
conservative_results = {}

for market_name, market_data in pending.items():
    if market_data is None:
        continue
    # Extract predictive_conservative (fallback to predictive for compatibility)
    pred = market_data.get("predictive_conservative") or market_data.get("predictive")
    if not pred:
        print(f"⚠️ {market_name}: no predictive_conservative data")
        continue

    base = {
        "market": market_data["market"],
        "assets": market_data["assets"],
        "days": market_data["days"],
        "oracle": market_data["oracle"],
        "bnh_btc": market_data["bnh_btc"]
    }
    conservative_results[market_name] = {**base, "predictive": pred}

with open(OUTPUT, "w") as f:
    json.dump(conservative_results, f, indent=2)
print(f"✅ Saved Conservative Best: {len(conservative_results)} markets, {os.path.getsize(OUTPUT)} bytes")

print("\n--- Conservative Results ---")
for m in ["TMN", "USDT", "GLOBAL"]:
    if m in conservative_results:
        p = conservative_results[m]["predictive"]
        print(f"  {m}: return={p.get('return', 0):.1f}%, sharpe={p.get('sharpe', 0):.2f}, dd={p.get('dd', 0):.1f}%")
