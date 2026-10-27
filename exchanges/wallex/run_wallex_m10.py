import subprocess
import sys

print("=== Running Wallex M10 Bots Full Cycle ===")

print("\n[1/2] Running M10 HODL Bot...")
subprocess.run([sys.executable, "exchanges/wallex/paper_trade_m10.py"])

print("\n[2/2] Running M10-Dividend Bot...")
subprocess.run([sys.executable, "exchanges/wallex/paper_m10_dividend.py"])

print("\n=== Cycle Complete ===")
