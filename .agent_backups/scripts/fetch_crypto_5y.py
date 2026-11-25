"""Fetch 5y crypto prices from Yahoo + reconstruct TMN pairs."""
import yfinance as yf
import json
import os

SYMBOLS = ['BTC-USD', 'ETH-USD', 'BNB-USD', 'XRP-USD', 'SOL-USD',
           'ADA-USD', 'DOGE-USD', 'DOT-USD', 'LINK-USD', 'AVAX-USD',
           'TRX-USD', 'LTC-USD', 'BCH-USD', 'POL-USD']

def main():
    os.makedirs("data", exist_ok=True)
    data = {}
    for sym in SYMBOLS:
        try:
            hist = yf.Ticker(sym).history(period="5y", interval="1d")
            if len(hist) > 100:
                data[sym] = {
                    ts.strftime("%Y-%m-%d"): float(close)
                    for ts, close in hist["Close"].items()
                    if close > 0
                }
                print(f"OK {sym}: {len(data[sym])} days")
            else:
                print(f"SKIP {sym}: only {len(hist)} days")
        except Exception as e:
            print(f"FAIL {sym}: {str(e)[:80]}")
    with open("data/crypto_5y_usd.json", "w") as f:
        json.dump(data, f)
    print(f"\nSaved {len(data)} symbols to data/crypto_5y_usd.json")

if __name__ == "__main__":
    main()
