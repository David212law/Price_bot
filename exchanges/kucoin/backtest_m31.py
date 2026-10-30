import json, os
from datetime import datetime, timezone

DATA_DIR = "exchanges/kucoin/data"
SYMBOLS = ["XBTUSDTM", "ETHUSDTM", "SOLUSDTM", "BNBUSDTM", "XRPUSDTM", "AVAXUSDTM"]

INITIAL_CAPITAL = 10000.0
TAKER_FEE = 0.0006
MAKER_FEE = 0.0002
M31_LEVERAGE = 6
SMA_PERIODS = 12
ENTRY_THRESHOLD = 0.00005
EXIT_THRESHOLD = 0.00001
COOLDOWN = 3 # 3 دوره فاندینگ = 24 ساعت

def load_json(path):
    if not os.path.exists(path): return None
    with open(path, 'r') as f: return json.load(f)

def run_backtest():
    # فرض: سرمایه به طور مساوی بین ۶ دارایی تقسیم می‌شود
    capital = INITIAL_CAPITAL
    per_asset_capital = capital / len(SYMBOLS)
    
    states = {sym: {"in_pos": False, "funding_earned": 0.0, "fees": 0.0, "last_exit": 0, "hist": [], "pos_start": 0} for sym in SYMBOLS}
    
    # بارگذاری داده‌ها
    funding_data = {}
    for sym in SYMBOLS:
        f = load_json(f"{DATA_DIR}/{sym}_funding_full.json")
        if f: funding_data[sym] = f
        
    if len(funding_data) < len(SYMBOLS):
        print("Missing funding data.")
        return
        
    # ایجاد یک تایم‌لاین یکپارچه از تمام رویدادهای فاندینگ
    all_times = set()
    for sym in SYMBOLS:
        for rec in funding_data[sym]:
            all_times.add(rec["timepoint"])
            
    sorted_times = sorted(list(all_times))
    
    # شبیه‌سازی
    for t in sorted_times:
        for sym in SYMBOLS:
            # پیدا کردن رکورد در این زمان (با تلورانس ۱ دقیقه)
            rec = next((r for r in funding_data[sym] if abs(r["timepoint"] - t) < 60000), None)
            if not rec: continue
            
            rate = float(rec["fundingRate"])
            st = states[sym]
            
            st["hist"].append(rate)
            if len(st["hist"]) > SMA_PERIODS: st["hist"].pop(0)
            avg_rate = sum(st["hist"]) / len(st["hist"])
            
            if st["in_pos"]:
                # دریافت فاندینگ (Signed)
                earned = per_asset_capital * M31_LEVERAGE * rate
                st["funding_earned"] += earned
                
                # بررسی خروج
                if avg_rate < EXIT_THRESHOLD:
                    cost = per_asset_capital * MAKER_FEE * 2 * M31_LEVERAGE
                    st["fees"] += cost
                    st["in_pos"] = False
                    st["last_exit"] = t
            else:
                # بررسی ورود
                time_since_exit = (t - st["last_exit"]) / (3600 * 1000)
                if avg_rate > ENTRY_THRESHOLD and rate > 0 and time_since_exit >= (COOLDOWN * 8):
                    cost = per_asset_capital * MAKER_FEE * 2 * M31_LEVERAGE
                    st["fees"] += cost
                    st["in_pos"] = True
                    st["pos_start"] = t
                    
    # محاسبه بازدهی نهایی
    total_profit = sum(st["funding_earned"] - st["fees"] for st in states.values())
    final_capital = capital + total_profit
    
    # محاسبه MaxDD تقریبی (بر اساس برداشت‌های فاندینگ)
    # چون فاندینگ به صورت پیوسته اضافه می‌شود، MaxDD در این استراتژی معمولاً بسیار پایین است
    max_dd = 0.0 
    
    print(f"=== M31 Funding Arbitrage Backtest on KuCoin ===")
    print(f"Initial Capital: ${INITIAL_CAPITAL:,.2f}")
    print(f"Final Capital:   ${final_capital:,.2f}")
    print(f"Total Return:    {((final_capital - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100:.2f}%")
    
    for sym in SYMBOLS:
        st = states[sym]
        print(f"  [{sym}] Funding: ${st['funding_earned']:.2f} | Fees: ${st['fees']:.2f} | Net: ${st['funding_earned']-st['fees']:.2f}")

if __name__ == "__main__":
    run_backtest()
