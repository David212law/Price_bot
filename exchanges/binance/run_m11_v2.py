import subprocess
import sys

print("=== Running M11-V2 Full Cycle ===")

print("\n[1/5] Generating M9 Signals...")
subprocess.run([sys.executable, "exchanges/binance/paper_trade_m9.py"])

print("\n[2/5] Generating Lead-Lag Signals...")
subprocess.run([sys.executable, "exchanges/binance/shadow_lead_lag.py"])

print("\n[3/5] Generating VSB Signals...")
subprocess.run([sys.executable, "exchanges/binance/vsb_generator.py"])

print("\n[4/5] Generating Grid Signals...")
subprocess.run([sys.executable, "exchanges/binance/grid_generator.py"])

print("\n[5/5] Running M11-V2 Allocator...")
subprocess.run([sys.executable, "exchanges/binance/m11_v2_paper_allocator.py"])

print("\n=== Cycle Complete ===")
