"""D-529: Unified Researcher — 4-stage pipeline.

Stages:
  1. filter_candidates (noise filter)
  2. thesis_detection (economic logic)
  3. thesis_dedup (remove clones)
  4. multi_layer_portfolio (combine + validate)

Outputs:
  - thesis_evidence.json
  - thesis_deduped.json
  - multi_layer_portfolio.json
  - pending_approvals.json (append)
  - Bale notification for PASS/MARGINAL
"""
import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone
import requests

BALE_TOKEN = os.environ.get("BALE_BOT_TOKEN", "")
BALE_CHAT = os.environ.get("BALE_CHAT_ID", "")


def send_bale(msg):
    if not BALE_TOKEN or not BALE_CHAT:
        print(f"[BALE-SKIP] {msg[:80]}")
        return
    try:
        requests.post(f"https://tapi.bale.ai/bot{BALE_TOKEN}/sendMessage",
                      json={"chat_id": BALE_CHAT, "text": msg}, timeout=10)
    except Exception as e:
        print(f"[BALE-ERR] {e}")


def run_stage_1():
    print("\n" + "="*70)
    print(" STAGE 1: filter_candidates (noise filter)")
    print("="*70)
    from research_lab.composer import load_state, filter_candidates
    state = load_state()
    total = 0
    for exchange in ["hyperliquid", "aster", "kucoin"]:
        for regime in ["TREND", "RANGE", "NEUTRAL"]:
            cands = filter_candidates(state, regime, exchange)
            total += len(cands)
            print(f"  {exchange}/{regime}: {len(cands)} candidates")
    print(f"  Total candidate slots: {total}")
    return total


def run_stage(name, module):
    print("\n" + "="*70)
    print(f" STAGE {name}")
    print("="*70)
    r = subprocess.run([sys.executable, "-m", module],
                       capture_output=True, text=True, cwd=".")
    if r.returncode != 0:
        print(f"  ⚠️ Failed: {r.stderr[:300]}")
        return False
    # Print last 10 lines of stdout
    for line in r.stdout.strip().split("\n")[-10:]:
        print(f"  {line}")
    return True


def write_pending(portfolio_data):
    if not portfolio_data:
        return
    verdict = portfolio_data.get("verdict")
    if verdict not in ("PASS", "MARGINAL"):
        print(f"  [PENDING] Skipped (verdict={verdict})")
        return
    pending_path = Path("exchanges/pending_approvals.json")
    pending_path.parent.mkdir(parents=True, exist_ok=True)
    pending = {}
    if pending_path.exists():
        try:
            pending = json.loads(pending_path.read_text())
        except:
            pending = {}
    key = f"mlp_portfolio_{datetime.now(timezone.utc).strftime('%Y%m%d')}"
    pending[key] = {
        "type": "multi_layer_portfolio",
        "verdict": verdict,
        "weights": portfolio_data["weights"],
        "validation": portfolio_data["validation"],
        "detected_at": datetime.now(timezone.utc).isoformat(),
    }
    pending_path.write_text(json.dumps(pending, indent=2))
    print(f"  [PENDING] Added {key}")
    send_bale(f"🔔 Researcher V2 — {verdict}\n"
              f"Improvement: {portfolio_data['validation']['improvement_pct']:+.1f}%\n"
              f"Coverage: {portfolio_data['validation']['coverage']:.0%}")


def main():
    print("="*70)
    print(f" RESEARCHER V2 — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("="*70)

    s1 = run_stage_1()
    if s1 == 0:
        print("\n❌ No candidates. Abort.")
        return

    if not run_stage("2: thesis_detection", "research_lab.thesis_detection"):
        return
    if not run_stage("3: thesis_dedup", "research_lab.thesis_dedup"):
        return
    if not run_stage("4: multi_layer_portfolio", "research_lab.multi_layer_portfolio"):
        return
    if not run_stage("5: improve_strategy", "research_lab.improve_strategy"):
        print("  (improve_strategy optional, continuing)")

    p = Path("research_lab/logs/multi_layer_portfolio.json")
    if p.exists():
        portfolio = json.loads(p.read_text())
        write_pending(portfolio)

    print("\n" + "="*70)
    print(" RESEARCHER V2 — DONE")
    print("="*70)
    print("Paper bots continue unchanged. Research-only.")


if __name__ == "__main__":
    main()
