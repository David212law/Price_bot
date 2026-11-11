"""Fetch Binance 2022 data for bear market testing."""
import urllib.request, json, os, zipfile, io
import pandas as pd
from datetime import datetime

COINS = ["BTC", "ETH", "BNB", "XRP", "SOL", "DOGE", "ADA", "AVAX", "LINK", "MATIC"]
MONTHS = ["2022-01", "2022-02", "2022-03", "2022-04", "2022-05", "2022-06",
          "2022-07", "2022-08", "2022-09", "2022-10", "2022-11", "2022-12"]

def fetch_klines(symbol, month):
    url = f"https://data.binance.vision/data/spot/monthly/klines/{symbol}USDT/1d/{symbol}USDT-1d-{month}.zip"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=15).read()
        z = zipfile.ZipFile(io.BytesIO(data))
        csv_name = z.namelist()[0]
        df = pd.read_csv(z.open(csv_name), header=None)
        # Binance format: [open_time, open, high, low, close, volume, ...]
        df.columns = ["ts", "o", "h", "l", "c", "v"] + [f"x{i}" for i in range(df.shape[1]-6)]
        df["date"] = pd.to_datetime(df["ts"], unit="ms").dt.strftime("%Y-%m-%d")
        df["c"] = df["c"].astype(float)
        return df.set_index("date")["c"]
    except Exception as e:
        return None

def main():
    os.makedirs("data", exist_ok=True)
    result = {}
    for coin in COINS:
        print(f"Fetching {coin}...")
        series = {}
        for month in MONTHS:
            s = fetch_klines(coin, month)
            if s is not None:
                series.update(s.to_dict())
        if series:
            result[f"{coin}-USD"] = series
            print(f"  ✅ {coin}: {len(series)} days")
    json.dump(result, open("data/crypto_2022_bear.json", "w"))
    print(f"\n✅ Saved {len(result)} coins to data/crypto_2022_bear.json")

if __name__ == "__main__":
    main()
