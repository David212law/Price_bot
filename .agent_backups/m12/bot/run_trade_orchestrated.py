import json, os, re, subprocess, sys, hashlib

CORE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # m12/
BOT_DIR = os.path.dirname(os.path.abspath(__file__))  # m12/bot

CONFIG = os.path.join(CORE, "config.json")

def config_hash():
    with open(CONFIG, "r") as f:
        return hashlib.md5(f.read().encode()).hexdigest()[:8]

def run(cmd):
    print(">>", " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=BOT_DIR, check=False, text=True, capture_output=True)

def extract_total_pnl_and_kill(output: str):
    # total_pnl: 774.5438
    # kill: False
    pnl = None
    kill = None

    m_pnl = re.search(r"total_pnl:\s*([+-]?\d+(\.\d+)?)", output)
    if m_pnl:
        pnl = float(m_pnl.group(1))

    m_kill = re.search(r"kill:\s*(True|False)", output)
    if m_kill:
        kill = (m_kill.group(1) == "True")

    return pnl, kill

def main():
    if not os.path.exists(CONFIG):
        print("No config.json found. Run researcher first.", flush=True)
        sys.exit(2)

    h = config_hash()
    print(f"[orchestrator] using config_hash={h}", flush=True)

    # Gate سریع قبل از اجرای واقعی bot
    # (همون مدل Gate که روی ترموس جواب داد: window=240 + fee_mode=default + max_pos=2)
    gate_cmd = [
        sys.executable, "-u", "paper_sim.py",
        "--window", "240",
        "--max_pos", "2",
        "--fee_mode", "default",
    ]
    r = run(gate_cmd)
    print(r.stdout)
    print(r.stderr, file=sys.stderr)

    pnl, kill = extract_total_pnl_and_kill(r.stdout + "\n" + r.stderr)
    if pnl is None or kill is None:
        print("[orchestrator] Could not parse gate output; aborting.", flush=True)
        sys.exit(3)

    print(f"[orchestrator] gate result: total_pnl={pnl}, kill={kill}", flush=True)

    if kill or pnl <= 0:
        print("[orchestrator] Gate failed; bot will not start.", flush=True)
        sys.exit(4)

    # فقط بعد از pass شدن Gate -> اجرای واقعی bot
    bot_cmd = [sys.executable, "-u", "bot.py"]
    r2 = subprocess.run(bot_cmd, cwd=BOT_DIR, check=False, text=True)
    sys.exit(r2.returncode)

if __name__ == "__main__":
    main()
