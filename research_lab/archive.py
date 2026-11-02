"""D-450: Archive composer runs + discoveries + signature cache."""
import os, json, shutil
from datetime import datetime, timezone

LOGS_DIR = "research_lab/logs"
HISTORY_DIR = os.path.join(LOGS_DIR, "history")
DISCOVERIES_PATH = os.path.join(LOGS_DIR, "discoveries.json")
SIGNATURES_CACHE_PATH = os.path.join(LOGS_DIR, "signatures_cache.json")


def archive_run():
    """Copy current report files into history/YYYY-MM-DD/."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    day_dir = os.path.join(HISTORY_DIR, today)
    os.makedirs(day_dir, exist_ok=True)
    files_to_archive = [
        ("research_lab/logs/composer_full_report.json", "composer_full_report.json"),
        ("research_lab/logs/composer_summary.md", "composer_summary.md"),
        ("exchanges/pending_approvals.json", "pending_approvals.json"),
        ("exchanges/portfolio_by_regime.json", "portfolio_by_regime.json"),
    ]
    archived = 0
    for src, dst_name in files_to_archive:
        if os.path.exists(src):
            try:
                shutil.copy(src, os.path.join(day_dir, dst_name))
                archived += 1
            except Exception as e:
                print(f"  ⚠️ archive {src}: {e}")
    print(f"✅ Archived {archived} files to {day_dir}/")
    return day_dir


def append_discoveries():
    """Append new STRICT/WEAK_PASS combos to append-only discoveries log."""
    pending_path = "exchanges/pending_approvals.json"
    if not os.path.exists(pending_path):
        return 0
    try:
        pending = json.load(open(pending_path))
    except Exception:
        return 0

    existing = []
    if os.path.exists(DISCOVERIES_PATH):
        try:
            existing = json.load(open(DISCOVERIES_PATH))
        except Exception:
            existing = []

    # Build key set for dedupe
    seen = set()
    for e in existing:
        seen.add((e.get("date"), e.get("exchange_regime")))

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    added = 0
    for ex_reg, entry in pending.items():
        key = (today, ex_reg)
        if key in seen:
            continue
        combo = entry.get("combo", {})
        record = {
            "date": today,
            "exchange_regime": ex_reg,
            "status": entry.get("status"),
            "combined_sharpe": combo.get("combined_sharpe"),
            "n_days": combo.get("n_days"),
            "max_dd_combo_pct": combo.get("max_dd_combo_pct"),
            "components": [
                {"name": c.get("name"), "weight": c.get("weight"),
                 "family": c.get("family"), "corr": c.get("corr")}
                for c in combo.get("components", [])
            ],
            "reasons": entry.get("reasons", []),
            "detected_at": entry.get("detected_at"),
        }
        existing.append(record)
        added += 1

    if added > 0:
        os.makedirs(os.path.dirname(DISCOVERIES_PATH), exist_ok=True)
        with open(DISCOVERIES_PATH, "w") as f:
            json.dump(existing, f, indent=2, default=str)
    print(f"✅ Discoveries: +{added} new (total {len(existing)})")
    return added


def update_signature_cache(state):
    """Cache strategy signatures (skip recompute if cached today)."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cache = {}
    if os.path.exists(SIGNATURES_CACHE_PATH):
        try:
            cache = json.load(open(SIGNATURES_CACHE_PATH))
        except Exception:
            cache = {}

    # Only cache fresh (not already cached today)
    try:
        from research_lab.strategy_signature import signature_for_entry
    except Exception:
        print("⚠️ signature module not available")
        return 0

    added = 0
    for key, v in state["done"].items():
        if not isinstance(v, dict): continue
        cache_key = key
        if cache_key in cache and cache[cache_key].get("cached_at") == today:
            continue
        try:
            sig = signature_for_entry(v)
            sig["cached_at"] = today
            cache[cache_key] = sig
            added += 1
        except Exception:
            continue

    if added > 0:
        os.makedirs(os.path.dirname(SIGNATURES_CACHE_PATH), exist_ok=True)
        with open(SIGNATURES_CACHE_PATH, "w") as f:
            json.dump(cache, f, indent=2, default=str)
    print(f"✅ Signatures cached: +{added} (total {len(cache)})")
    return added
