"""D-539: Economic Generator

Reads economic_library.json and produces strategy definitions.
Does NOT run backtests — only produces specs.
The actual backtests run in economic_runner.py.

Output: research_lab/logs/generated/economic_v1_definitions.json
"""
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone

LIB_PATH = Path("research_lab/economic_library.json")
OUT_PATH = Path("research_lab/logs/generated/economic_v1_definitions.json")


def stable_hash(obj):
    """Deterministic short hash of a params dict."""
    s = json.dumps(obj, sort_keys=True)
    return hashlib.sha256(s.encode()).hexdigest()[:8]


def main():
    print("=" * 72)
    print(" ECONOMIC GENERATOR — D-539")
    print("=" * 72)

    if not LIB_PATH.exists():
        print(f"❌ {LIB_PATH} not found")
        return

    lib = json.loads(LIB_PATH.read_text())
    definitions = []
    n_skipped = 0

    for logic in lib["logics"]:
        if logic["status"] != "implemented":
            n_skipped += len(logic["variants"])
            continue
        for i, variant in enumerate(logic["variants"]):
            params = dict(variant)
            params["logic_id"] = logic["id"]
            h = stable_hash(params)
            definitions.append({
                "strategy": f"ECO_{logic['id'].upper()}",
                "logic_id": logic["id"],
                "params": params,
                "hash": h,
                "data_source": logic["data_source"],
                "thesis": logic["thesis"],
            })

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "version": lib["version"],
        "n_definitions": len(definitions),
        "n_skipped_todo": n_skipped,
        "definitions": definitions,
    }, indent=2))

    print(f"  ✅ Generated {len(definitions)} strategy definitions")
    print(f"  ⏭  Skipped {n_skipped} variants (logic status=todo)")
    print(f"  💾 {OUT_PATH}")


if __name__ == "__main__":
    main()
