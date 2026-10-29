import requests
import time

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json"
}

def probe_endpoint(name, url, is_post=False, payload=None):
    print(f"Testing {name} ({url})...")
    try:
        start_time = time.time()
        if is_post:
            r = requests.post(url, json=payload, headers=HEADERS, timeout=10)
        else:
            r = requests.get(url, headers=HEADERS, timeout=10)
            
        latency = (time.time() - start_time) * 1000
        print(f"  [Status: {r.status_code}] Latency: {latency:.0f}ms")
        
        if r.status_code == 200:
            print(f"  ✅ SUCCESS! Response (truncated): {r.text[:100]}...")
        else:
            print(f"  ❌ Blocked/Error: {r.text[:100].replace(chr(10), ' ')}")
            
    except requests.exceptions.ConnectionError as ce:
        if "NameResolutionError" in str(ce) or "Failed to resolve" in str(ce):
            print(f"  [DNS Error] Failed to resolve hostname.")
        else:
            print(f"  [Connection Error] {str(ce)[:100]}")
    except Exception as e:
        print(f"  [Failed] Exception: {str(e)[:100]}")
    print("-" * 50)

def main():
    print("=== Multi-Exchange Connectivity Probe (AgentBroker, KuCoin, KCEX, Ourbit) ===")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    print("=" * 50)
    
    # 1. Hyperliquid (شاهد - متد POST)
    probe_endpoint("Hyperliquid Control", "https://api.hyperliquid.xyz/info", is_post=True, payload={"type": "meta"})
    
    # 2. AgentBroker (تست اندپوینت‌های عمومی احتمالی)
    probe_endpoint("AgentBroker Markets", "https://agentbroker.polsia.app/api/v1/markets")
    
    # 3. KuCoin (صرافی متمرکز با نقدینگی بالا)
    probe_endpoint("KuCoin Tickers", "https://api.kucoin.com/api/v1/market/allTickers")
    
    # 4. KCEX (صرافی متمرکز)
    probe_endpoint("KCEX Tickers", "https://api.kcex.com/api/v1/market/allTickers")
    
    # 5. Ourbit (صرافی متمرکز)
    probe_endpoint("Ourbit Tickers", "https://api.ourbit.com/api/v1/market/tickers")

if __name__ == "__main__":
    main()
