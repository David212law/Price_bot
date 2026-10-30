import os, requests

def send_bale(msg):
    token = os.environ.get("BALE_BOT_TOKEN")
    chat_id = os.environ.get("BALE_CHAT_ID")
    if not token or not chat_id: 
        print(f"[BALE] Skipped: {msg[:80]}")
        return
    url = f"https://tapi.bale.ai/bot{token}/sendMessage"
    try: requests.post(url, json={"chat_id": chat_id, "text": msg}, timeout=10)
    except Exception as e: print(f"[BALE] Error: {e}")
