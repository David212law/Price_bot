import subprocess
import sys

print("=== Running M11-HL Full Cycle ===")

print("\n[1/5] Generating M31 Funding Signals...")
subprocess.run([sys.executable, "exchanges/hyperliquid/m31_funding_generator.py"])

print("\n[2/5] Generating M35 EMA Signals...")
subprocess.run([sys.executable, "exchanges/hyperliquid/m35_ema_generator.py"])

print("\n[3/5] Generating M40 Pullback Signals...")
subprocess.run([sys.executable, "exchanges/hyperliquid/m40_generator.py"])

print("\n[4/5] Generating M41 Volatility Breakout Signals...")
subprocess.run([sys.executable, "exchanges/hyperliquid/m41_generator.py"])

print("\n[5/5] Running M11-HL Allocator...")
subprocess.run([sys.executable, "exchanges/hyperliquid/m11_hl_allocator.py"])

print("\n=== Cycle Complete ===")
