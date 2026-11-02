"""D-478: Paper-Based Composer — uses actual Paper trading returns."""
import os, json, sys
sys.path.insert(0, '.')

STATE_DIRS = {
    "hyperliquid": "exchanges/hyperliquid/state",
    "aster": "exchanges/aster/state",
    "kucoin": "exchanges/kucoin/state"
}

def load_paper_history():
    """Load history of closed trades from all Paper bots."""
    all_trades = {}
    for ex, path in STATE_DIRS.items():
        if not os.path.exists(path): continue
        for f in os.listdir(path):
            if not f.endswith('.json') or 'portfolio' not in f: continue
            try:
                d = json.load(open(os.path.join(path, f)))
                hist = d.get('history', [])
                if hist:
                    bot_name = f.replace('.json', '')
                    all_trades[bot_name] = hist
            except:
                pass
    return all_trades

if __name__ == "__main__":
    trades = load_paper_history()
    if not trades:
        print("No closed trades in Paper yet. Wait for more data.")
    else:
        for bot, hist in trades.items():
            print(f"{bot}: {len(hist)} closed trades")
